"""Catalogue des outils integres + gestionnaire de taches (docker exec avec commandes en liste blanche)."""
import ipaddress, re, threading, time, uuid
from collections import deque

DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
SEG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_READ = 400_000


class ToolError(Exception):
    pass


def _ip(v):
    try:
        return str(ipaddress.ip_address(str(v).strip()))
    except ValueError:
        raise ToolError("Adresse IP invalide")


def _cidr(v):
    try:
        return str(ipaddress.ip_network(str(v).strip(), strict=False))
    except ValueError:
        raise ToolError("CIDR invalide")


def _domain(v):
    v = str(v).strip().lower()
    if not DOMAIN_RE.match(v):
        raise ToolError("Nom de domaine invalide")
    return v


def _wt(task):
    code = ("import os,sys,urllib.request as u;"
            "r=u.Request('http://127.0.0.1:8830/run/'+sys.argv[1],method='POST',"
            "headers={'X-AI-Gateway-Token':os.environ['AI_GATEWAY_TOKEN']});"
            "print(u.urlopen(r,timeout=20).read().decode())")
    return lambda p: (["python", "-c", code, task], {})


TOOLS = {
    "scanner": {
        "title": "Scanner de ports", "codename": "GREEN ARROW", "container": "green-arrow", "icon": "radar",
        "desc": "Audit des ports locaux, découverte ARP et scan TCP/nmap. Cibles limitées à AUTHORIZED_CIDRS.",
        "warning": "Usage strictement limité aux réseaux que vous possédez ou êtes autorisé à auditer (art. 323-1 Code pénal).",
        "actions": [
            {"id": "local", "label": "Audit des ports locaux", "desc": "Sockets en écoute du conteneur (psutil).",
             "params": [], "timeout": 120, "build": lambda p: (["python3", "/app/tool_cli.py", "local"], {})},
            {"id": "discover", "label": "Découverte réseau (ARP)", "desc": "Liste les équipements d'un sous-réseau autorisé.",
             "params": [{"name": "cidr", "label": "Sous-réseau", "type": "select", "source": "cidrs"}], "timeout": 300,
             "build": lambda p: (["python3", "/app/tool_cli.py", "discover", _cidr(p["cidr"])], {})},
            {"id": "nmap", "label": "nmap rapide (top 100 + versions)", "desc": "Détection de services sur une machine autorisée.",
             "params": [{"name": "ip", "label": "Adresse IP", "type": "text", "placeholder": "192.168.1.10"}], "timeout": 900,
             "confirm": "Lancer nmap sur cette cible ? Elle doit être dans votre périmètre autorisé.",
             "build": lambda p: (["python3", "/app/tool_cli.py", "nmap", _ip(p["ip"])], {})},
            {"id": "portscan", "label": "Scan TCP complet (1-65535)", "desc": "Long et bruyant : peut déclencher IDS/pare-feu.",
             "params": [{"name": "ip", "label": "Adresse IP", "type": "text", "placeholder": "192.168.1.10"}], "timeout": 3600,
             "danger": True, "confirm": "Scan complet des 65 535 ports : bruyant et long. Cible autorisée uniquement. Continuer ?",
             "build": lambda p: (["python3", "/app/tool_cli.py", "portscan", _ip(p["ip"])], {})},
        ],
        "files": [{"id": "results", "label": "Résultats (CSV)", "dir": "/results"}],
    },
    "osint": {
        "title": "OSINT passif", "codename": "ORACLE", "container": "oracle-cti", "icon": "eye",
        "desc": "DNS, Certificate Transparency, TLS et en-têtes HTTP de vos domaines. Aucun scan actif.",
        "warning": "Uniquement vos domaines, ceux de clients avec accord, ou sources publiques.",
        "actions": [
            {"id": "run", "label": "Lancer un passage maintenant", "desc": "Un cycle complet sur tous les domaines.",
             "params": [], "timeout": 1800,
             "build": lambda p: (["python", "/app/osint/osint_veille.py"], {"HOME": "/data/home"})},
            {"id": "add", "label": "Ajouter un domaine", "desc": "Ajoute à la liste de surveillance.",
             "params": [{"name": "domain", "label": "Domaine", "type": "text", "placeholder": "exemple.fr"}], "timeout": 30,
             "build": lambda p: (["python", "/app/osint/osint_veille.py", "--add", _domain(p["domain"])], {"HOME": "/data/home"})},
            {"id": "remove", "label": "Retirer un domaine", "desc": "Retire de la liste de surveillance.",
             "params": [{"name": "domain", "label": "Domaine", "type": "select", "source": "domains"}], "timeout": 30,
             "build": lambda p: (["python", "/app/tool_cli.py", "remove", _domain(p["domain"])], {"HOME": "/data/home"})},
        ],
        "files": [{"id": "reports", "label": "Rapports", "dir": "/data/home/veille-osint/rapports"},
                  {"id": "state", "label": "Domaines, état, journal", "dir": "/data/home/veille-osint"}],
        "sources": {"domains": {"file": "/data/home/veille-osint/domaines.txt"}},
    },
    "veille": {
        "title": "Veille cyber", "codename": "WATCHTOWER", "container": "justice-league-watchtower", "icon": "newspaper",
        "desc": "Flux RSS cyber (CERT-FR, CISA…), CVE NVD/KEV, rapports quotidiens et hebdomadaires.",
        "actions": [
            {"id": "run", "label": "Passage veille RSS maintenant", "desc": "Un passage de veille_cyber.py.",
             "params": [], "timeout": 600,
             "build": lambda p: (["python", "/app/veille-cyber/veille_cyber.py", "--once"], {"VEILLE_DIR": "/data/veille-cyber"})},
            {"id": "wt_fetch", "label": "WATCHTOWER · collecte flux", "desc": "Déclenche la tâche fetch.", "params": [], "timeout": 60, "build": _wt("fetch")},
            {"id": "wt_kev", "label": "WATCHTOWER · CISA KEV", "desc": "Vulnérabilités exploitées activement.", "params": [], "timeout": 60, "build": _wt("kev")},
            {"id": "wt_nvd", "label": "WATCHTOWER · NVD", "desc": "CVE récentes selon NVD_MIN_CVSS.", "params": [], "timeout": 60, "build": _wt("nvd")},
            {"id": "wt_daily", "label": "WATCHTOWER · rapport quotidien", "desc": "Génère le rapport du jour.", "params": [], "timeout": 60, "build": _wt("daily")},
            {"id": "wt_weekly", "label": "WATCHTOWER · rapport hebdo", "desc": "Génère le rapport de la semaine.", "params": [], "timeout": 60, "build": _wt("weekly")},
        ],
        "files": [{"id": "reports", "label": "Rapports veille RSS", "dir": "/data/veille-cyber/rapports"},
                  {"id": "wt", "label": "Rapports WATCHTOWER", "dir": "/data/reports"}],
        "link": {"label": "Ouvrir l'interface WATCHTOWER", "url": "http://127.0.0.1:8830"},
    },
}


def public_catalogue():
    out = []
    for tid, t in TOOLS.items():
        out.append({
            "id": tid, **{k: t[k] for k in ("title", "codename", "container", "icon", "desc")},
            "warning": t.get("warning", ""), "link": t.get("link"),
            "actions": [{k: a.get(k) for k in ("id", "label", "desc", "params", "danger", "confirm")} for a in t["actions"]],
            "files": t["files"],
        })
    return out


def find_action(tool, action):
    t = TOOLS.get(tool)
    if not t:
        raise ToolError("Outil inconnu")
    for a in t["actions"]:
        if a["id"] == action:
            return t, a
    raise ToolError("Action inconnue")


def safe_rel(rel):
    parts = [s for s in (rel or "").split("/") if s]
    if len(parts) > 3 or any(not SEG_RE.match(s) or s in (".", "..") for s in parts):
        raise ToolError("Chemin invalide")
    return parts


def resolve_path(tool, root_id, rel):
    t = TOOLS.get(tool)
    root = next((f for f in (t or {}).get("files", []) if f["id"] == root_id), None)
    if not root:
        raise ToolError("Dossier inconnu")
    parts = safe_rel(rel)
    return root["dir"].rstrip("/") + ("/" + "/".join(parts) if parts else "")


# ------------------------------------------------------------------ docker exec
def exec_stream(client, container, cmd, env=None):
    """Genere des lignes de sortie ; le code retour est place dans la liste renvoyee en dernier element (tuple)."""
    ex = client.api.exec_create(container.id, cmd, environment=env or {}, stdout=True, stderr=True)
    buf = b""
    for chunk in client.api.exec_start(ex["Id"], stream=True):
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.decode("utf-8", "replace")
    if buf:
        yield buf.decode("utf-8", "replace")
    yield ("__exit__", client.api.exec_inspect(ex["Id"]).get("ExitCode"))


def exec_text(client, container, cmd, env=None, limit=MAX_READ):
    ex = client.api.exec_create(container.id, cmd, environment=env or {}, stdout=True, stderr=True)
    data = b""
    for chunk in client.api.exec_start(ex["Id"], stream=True):
        data += chunk
        if len(data) > limit:
            break
    return data.decode("utf-8", "replace"), client.api.exec_inspect(ex["Id"]).get("ExitCode")


# ------------------------------------------------------------------ jobs
class Job:
    def __init__(self, tool, action, label, params, user, container):
        self.id = uuid.uuid4().hex[:10]
        self.tool, self.action, self.label, self.params, self.user, self.container = tool, action, label, params, user, container
        self.status, self.exit = "running", None
        self.started, self.ended = time.time(), None
        self.lines = deque(maxlen=4000)
        self.total = 0

    def add(self, line):
        self.lines.append(line)
        self.total += 1

    def public(self, since=0, with_output=False):
        d = {"id": self.id, "tool": self.tool, "action": self.action, "label": self.label, "params": self.params,
             "user": self.user, "container": self.container, "status": self.status, "exit": self.exit,
             "started": self.started, "ended": self.ended, "total": self.total}
        if with_output:
            first = self.total - len(self.lines)
            start = max(since, first)
            d["lines"] = list(self.lines)[start - first:]
            d["next"] = self.total
        return d


class JobManager:
    def __init__(self, client, log):
        self.client, self.log = client, log
        self.jobs, self.lock = {}, threading.Lock()

    def running(self, tool, action):
        return any(j.status == "running" and j.tool == tool and j.action == action for j in self.jobs.values())

    def start(self, tool, action, params, user, container):
        t, a = find_action(tool, action)
        if self.running(tool, action):
            raise ToolError("Cette action est déjà en cours.")
        argv, env = a["build"](params or {})
        argv = ["timeout", "-s", "TERM", str(a.get("timeout", 600))] + argv
        job = Job(tool, action, a["label"], {k: str(v)[:120] for k, v in (params or {}).items()}, user, container.name)
        with self.lock:
            self.jobs[job.id] = job
            for old in sorted(self.jobs.values(), key=lambda j: j.started)[:-60]:
                if old.status != "running":
                    self.jobs.pop(old.id, None)
        self.log(f"AUDIT user={user} tool={tool} action={action} params={job.params} job={job.id}")
        threading.Thread(target=self._run, args=(job, container, argv, env), daemon=True).start()
        return job

    def _run(self, job, container, argv, env):
        try:
            for item in exec_stream(self.client, container, argv, env):
                if isinstance(item, tuple):
                    job.exit = item[1]
                else:
                    job.add(item)
            job.status = "ok" if job.exit == 0 else ("timeout" if job.exit == 124 else "error")
        except Exception as e:  # noqa
            job.add(f"[console] erreur: {e}")
            job.status = "error"
        job.ended = time.time()
        self.log(f"AUDIT job={job.id} status={job.status} exit={job.exit}")
