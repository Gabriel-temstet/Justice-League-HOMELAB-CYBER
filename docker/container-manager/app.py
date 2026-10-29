"""Justice League Console (Version Z) : gestion Docker + utilisation des outils integres.
Pas d'execution arbitraire : seules les actions Docker explicites et les commandes en liste blanche de tools.py."""
import base64, os, re, secrets, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import docker
from docker.errors import DockerException, NotFound, APIError
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import tools as T

USERNAME = os.getenv("SOC_ADMIN_USER", "admin")
PASSWORD = os.getenv("SOC_ADMIN_PASSWORD", "")
STATIC = Path(__file__).parent / "static"
client = docker.from_env()
app = FastAPI(title="Justice League Console", version="Z", docs_url=None, redoc_url=None, openapi_url=None)


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, file=sys.stdout, flush=True)


# ------------------------------------------------------------------ securite
_fails, _fails_lock = {}, threading.Lock()


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    ip = request.client.host if request.client else "?"
    if not PASSWORD:
        return JSONResponse({"detail": "Configure SOC_ADMIN_PASSWORD."}, status_code=503)
    with _fails_lock:
        n, t0 = _fails.get(ip, (0, 0))
        if n >= 8 and time.time() - t0 < 120:
            return JSONResponse({"detail": "Trop d'échecs, réessayez dans 2 minutes."}, status_code=429)
    user = None
    h = request.headers.get("authorization", "")
    if h.lower().startswith("basic "):
        try:
            u, _, p = base64.b64decode(h[6:]).decode().partition(":")
            if secrets.compare_digest(u, USERNAME) & secrets.compare_digest(p, PASSWORD):
                user = u
        except Exception:
            pass
    if not user:
        with _fails_lock:
            n, t0 = _fails.get(ip, (0, 0))
            _fails[ip] = (n + 1, time.time() if n == 0 or time.time() - t0 > 120 else t0)
        return JSONResponse({"detail": "Authentification requise"}, status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="Justice League Console"'})
    with _fails_lock:
        _fails.pop(ip, None)
    if request.method not in ("GET", "HEAD"):  # anti-CSRF : en-tete custom => preflight CORS, jamais autorise
        if request.headers.get("x-jlc") != "1":
            return JSONResponse({"detail": "Requête refusée (CSRF)"}, status_code=403)
    request.state.user = user
    resp = await call_next(request)
    resp.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                         "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'",
                         "Cache-Control": "no-store"})
    return resp


jobs = T.JobManager(client, log)

ROLES = {
    "martian-core": ("MARTIAN MANHUNTER", "Passerelle IA & corrélation"), "martian-db": ("MARTIAN DB", "Mémoire PostgreSQL"),
    "martian-ollama": ("OLLAMA", "Modèle IA local"), "batman-n8n": ("BATMAN", "Orchestration n8n"),
    "batman-postgres": ("BATMAN DB", "PostgreSQL n8n"), "batman-normalizer": ("BATMAN", "Normalisation des événements"),
    "green-lantern": ("GREEN LANTERN", "Notifications"), "justice-league-collectors": ("COLLECTORS", "Suricata / Zeek / Wazuh"),
    "oracle-cti": ("ORACLE", "CTI + OSINT passif"), "green-arrow": ("GREEN ARROW", "Découverte & scanner de ports"),
    "justice-league-soc": ("SOC COMMAND CENTER", "Tableau de bord SOC"), "justice-league-caddy": ("CADDY", "Proxy TLS local"),
    "justice-league-watchtower": ("WATCHTOWER", "Veille cyber"), "justice-league-bug-bounty": ("BUG BOUNTY LAB", "Environnement isolé"),
    "justice-league-container-manager": ("CONSOLE", "Cette interface"),
}
SECRET_RE = re.compile(r"PASS|TOKEN|KEY|SECRET|DSN|WEBHOOK|AUTH(?!ORIZED)|CREDENTIAL", re.I)


def dock(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except NotFound:
        raise HTTPException(404, "Introuvable")
    except APIError as e:
        raise HTTPException(409, f"Docker: {e.explanation or e}")
    except DockerException as e:
        raise HTTPException(503, f"Docker indisponible: {e}")


def get_container(name):
    if not name or len(name) > 128:
        raise HTTPException(400, "Nom invalide")
    return dock(client.containers.get, name)


# ------------------------------------------------------------------ stats
_stats_cache, _stats_lock = {}, threading.Lock()


def _stats_one(c):
    try:
        s = c.stats(stream=False)
        cpu = s["cpu_stats"]; pre = s["precpu_stats"]
        dcpu = cpu["cpu_usage"]["total_usage"] - pre.get("cpu_usage", {}).get("total_usage", 0)
        dsys = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
        ncpu = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage") or [1])
        pct = (dcpu / dsys * ncpu * 100) if dsys > 0 and dcpu >= 0 else 0.0
        m = s.get("memory_stats", {})
        used = m.get("usage", 0) - (m.get("stats", {}).get("inactive_file", m.get("stats", {}).get("cache", 0)))
        nets = s.get("networks") or {}
        return c.id, {"cpu": round(pct, 1), "mem": max(used, 0), "mem_limit": m.get("limit", 0),
                      "rx": sum(n["rx_bytes"] for n in nets.values()), "tx": sum(n["tx_bytes"] for n in nets.values()),
                      "pids": s.get("pids_stats", {}).get("current", 0)}
    except Exception:
        return c.id, None


def all_stats(running):
    with _stats_lock:
        if time.time() - _stats_cache.get("t", 0) < 4:
            return _stats_cache["d"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        d = dict(ex.map(_stats_one, running))
    with _stats_lock:
        _stats_cache.update(t=time.time(), d=d)
    return d


def summarize(c, stats=None):
    a = c.attrs; s = a.get("State", {}); cfg = a.get("Config", {})
    ports = []
    for p, binds in (a.get("NetworkSettings", {}).get("Ports") or {}).items():
        for b in (binds or []):
            ports.append(f'{b.get("HostIp", "")}:{b.get("HostPort")}→{p}')
    role = ROLES.get(c.name, ("", ""))
    return {"id": c.short_id, "name": c.name, "image": cfg.get("Image", ""), "status": c.status,
            "health": (s.get("Health") or {}).get("Status", ""), "started": s.get("StartedAt", ""),
            "restarts": a.get("RestartCount", 0), "exit_code": s.get("ExitCode"), "created": a.get("Created", ""),
            "ports": ports, "codename": role[0], "role": role[1],
            "service": cfg.get("Labels", {}).get("com.docker.compose.service", ""),
            "stats": (stats or {}).get(c.id)}


# ------------------------------------------------------------------ API
@app.get("/health")
def health():
    try:
        client.ping()
        return {"status": "ok", "service": "console", "version": "Z"}
    except DockerException:
        raise HTTPException(503, "Docker indisponible")


@app.get("/api/containers")
def containers(stats: bool = True):
    items = dock(client.containers.list, all=True)
    st = all_stats([c for c in items if c.status == "running"]) if stats else {}
    out = [summarize(c, st) for c in items]
    out.sort(key=lambda x: (x["status"] != "running", x["name"].lower()))
    return {"items": out, "count": len(out), "time": time.time()}


@app.get("/api/overview")
def overview():
    info = dock(client.info)
    items = dock(client.containers.list, all=True)
    st = all_stats([c for c in items if c.status == "running"])
    vals = [v for v in st.values() if v]
    return {"host": {"name": info.get("Name"), "os": info.get("OperatingSystem"), "kernel": info.get("KernelVersion"),
                     "cpus": info.get("NCPU"), "mem": info.get("MemTotal"), "docker": info.get("ServerVersion"),
                     "arch": info.get("Architecture")},
            "counts": {"total": len(items), "running": sum(c.status == "running" for c in items),
                       "stopped": sum(c.status in ("exited", "created", "dead") for c in items),
                       "paused": sum(c.status == "paused" for c in items), "images": info.get("Images", 0),
                       "unhealthy": [c.name for c in items if (c.attrs["State"].get("Health") or {}).get("Status") == "unhealthy"],
                       "restarting": [c.name for c in items if c.status == "restarting"]},
            "usage": {"cpu": round(sum(v["cpu"] for v in vals), 1), "mem": sum(v["mem"] for v in vals),
                      "rx": sum(v["rx"] for v in vals), "tx": sum(v["tx"] for v in vals)},
            "time": time.time()}


@app.get("/api/containers/{name}")
def container_detail(name: str):
    c = get_container(name)
    a = c.attrs; cfg = a.get("Config", {}); hc = a.get("HostConfig", {})
    env = []
    for e in cfg.get("Env") or []:
        k, _, v = e.partition("=")
        env.append({"key": k, "value": "••••••••" if SECRET_RE.search(k) else v})
    nets = {n: {"ip": v.get("IPAddress"), "aliases": v.get("Aliases")} for n, v in (a["NetworkSettings"].get("Networks") or {}).items()}
    mounts = [{"type": m.get("Type"), "src": m.get("Name") or m.get("Source"), "dst": m.get("Destination"), "rw": m.get("RW")} for m in a.get("Mounts", [])]
    health = a["State"].get("Health") or {}
    d = summarize(c, all_stats([c]) if c.status == "running" else {})
    d.update({"cmd": cfg.get("Cmd"), "entrypoint": cfg.get("Entrypoint"), "user": cfg.get("User") or "root", "env": env,
              "mounts": mounts, "networks": nets, "restart_policy": (hc.get("RestartPolicy") or {}).get("Name"),
              "read_only": hc.get("ReadonlyRootfs"), "cap_add": hc.get("CapAdd"), "cap_drop": hc.get("CapDrop"),
              "privileged": hc.get("Privileged"), "healthcheck": [{"end": h.get("End"), "code": h.get("ExitCode"), "out": (h.get("Output") or "")[-300:]}
                                                                  for h in (health.get("Log") or [])[-5:]],
              "labels": {k: v for k, v in cfg.get("Labels", {}).items() if k.startswith("com.docker.compose")}})
    return d


class Action(BaseModel):
    action: str = Field(pattern="^(start|stop|restart|pause|unpause)$")


@app.post("/api/containers/{name}/action")
def container_action(name: str, body: Action, request: Request):
    c = get_container(name)
    if c.name == "justice-league-container-manager" and body.action in ("stop", "pause"):
        raise HTTPException(400, "La console ne peut pas s'arrêter elle-même.")
    log(f"AUDIT user={request.state.user} container={c.name} action={body.action}")
    fn = {"start": c.start, "stop": lambda: c.stop(timeout=15), "restart": lambda: c.restart(timeout=15),
          "pause": c.pause, "unpause": c.unpause}[body.action]
    dock(fn)
    c.reload()
    return {"ok": True, "name": c.name, "status": c.status}


@app.get("/api/containers/{name}/logs")
def container_logs(name: str, tail: int = Query(200, ge=1, le=2000), since: int = Query(0, ge=0)):
    c = get_container(name)
    raw = dock(c.logs, tail=tail, since=since or None, timestamps=True, stdout=True, stderr=True)
    return {"name": c.name, "lines": raw.decode("utf-8", "replace").splitlines()}


@app.get("/api/images")
def images():
    used = {}
    for c in dock(client.containers.list, all=True):
        used.setdefault(c.attrs["Image"], []).append(c.name)
    out = [{"id": i.short_id.replace("sha256:", ""), "tags": i.tags, "size": i.attrs.get("Size", 0),
            "created": i.attrs.get("Created", ""), "used_by": used.get(i.id, [])} for i in dock(client.images.list)]
    return {"items": sorted(out, key=lambda x: x["created"], reverse=True)}


@app.get("/api/volumes")
def volumes():
    used = {}
    for c in dock(client.containers.list, all=True):
        for m in c.attrs.get("Mounts", []):
            if m.get("Name"):
                used.setdefault(m["Name"], []).append(c.name)
    return {"items": [{"name": v.name, "driver": v.attrs.get("Driver"), "created": v.attrs.get("CreatedAt", ""),
                       "used_by": used.get(v.name, [])} for v in dock(client.volumes.list)]}


@app.get("/api/networks")
def networks():
    out = []
    for n in dock(client.networks.list):
        n.reload()
        cfg = (n.attrs.get("IPAM", {}).get("Config") or [{}])
        out.append({"name": n.name, "driver": n.attrs.get("Driver"), "subnet": cfg[0].get("Subnet", ""),
                    "containers": sorted(v.get("Name", "") for v in (n.attrs.get("Containers") or {}).values())})
    return {"items": out}


# ------------------------------------------------------------------ outils
def _tool_container(tool):
    try:
        t = T.TOOLS[tool]
    except KeyError:
        raise HTTPException(404, "Outil inconnu")
    try:
        c = client.containers.get(t["container"])
    except NotFound:
        raise HTTPException(409, f"Conteneur {t['container']} introuvable : déployez la stack.")
    if c.status != "running":
        raise HTTPException(409, f"Le conteneur {c.name} n'est pas démarré (état : {c.status}).")
    return t, c


def _env_of(c, key):
    for e in c.attrs["Config"].get("Env") or []:
        if e.startswith(key + "="):
            return e.split("=", 1)[1]
    return ""


@app.get("/api/tools")
def tools_list():
    out = []
    for t in T.public_catalogue():
        try:
            c = client.containers.get(t["container"]); t["state"] = c.status
            t["health"] = (c.attrs["State"].get("Health") or {}).get("Status", "")
            t["cidrs"] = _env_of(c, "AUTHORIZED_CIDRS").split() if t["id"] == "scanner" else []
        except DockerException:
            t["state"] = "absent"; t["health"] = ""; t["cidrs"] = []
        out.append(t)
    return {"items": out}


@app.get("/api/tools/{tool}/options/{source}")
def tool_options(tool: str, source: str):
    t, c = _tool_container(tool)
    if source == "cidrs":
        return {"items": _env_of(c, "AUTHORIZED_CIDRS").split()}
    src = (t.get("sources") or {}).get(source)
    if not src:
        raise HTTPException(404, "Source inconnue")
    txt, _ = T.exec_text(client, c, ["cat", "--", src["file"]], env={"HOME": "/data/home"})
    return {"items": [l.strip() for l in txt.splitlines() if l.strip() and not l.startswith("#")]}


class Run(BaseModel):
    params: dict = {}


@app.post("/api/tools/{tool}/{action}")
def tool_run(tool: str, action: str, body: Run, request: Request):
    t, c = _tool_container(tool)
    try:
        job = jobs.start(tool, action, body.params, request.state.user, c)
    except T.ToolError as e:
        raise HTTPException(400, str(e))
    return job.public()


@app.get("/api/jobs")
def jobs_list():
    return {"items": [j.public() for j in sorted(jobs.jobs.values(), key=lambda j: j.started, reverse=True)]}


@app.get("/api/jobs/{jid}")
def job_get(jid: str, since: int = Query(0, ge=0)):
    j = jobs.jobs.get(jid)
    if not j:
        raise HTTPException(404, "Tâche introuvable")
    return j.public(since, with_output=True)


@app.get("/api/tools/{tool}/files")
def files_list(tool: str, root: str, path: str = ""):
    t, c = _tool_container(tool)
    try:
        p = T.resolve_path(tool, root, path)
    except T.ToolError as e:
        raise HTTPException(400, str(e))
    txt, code = T.exec_text(client, c, ["ls", "-1Apt", "--", p])
    if code != 0:
        return {"items": [], "path": path}
    items = []
    for line in txt.splitlines():
        line = line.strip()
        if line:
            items.append({"name": line.rstrip("/"), "dir": line.endswith("/")})
    return {"items": items[:500], "path": path}


@app.get("/api/tools/{tool}/file")
def file_get(tool: str, root: str, path: str, download: bool = False):
    t, c = _tool_container(tool)
    try:
        p = T.resolve_path(tool, root, path)
    except T.ToolError as e:
        raise HTTPException(400, str(e))
    if download:
        ex = client.api.exec_create(c.id, ["cat", "--", p], stdout=True, stderr=False)
        gen = client.api.exec_start(ex["Id"], stream=True)
        name = path.split("/")[-1]
        return StreamingResponse(gen, media_type="application/octet-stream",
                                 headers={"Content-Disposition": f'attachment; filename="{name}"'})
    txt, code = T.exec_text(client, c, ["head", "-c", str(T.MAX_READ), "--", p])
    if code != 0:
        raise HTTPException(404, "Fichier introuvable")
    return {"path": path, "content": txt, "truncated": len(txt) >= T.MAX_READ}


# ------------------------------------------------------------------ UI
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
