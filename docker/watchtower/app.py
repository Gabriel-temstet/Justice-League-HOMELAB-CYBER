"""WATCHTOWER — veille technologique cyber automatisée pour le homelab Justice League.

Tourne en continu : collecte RSS/Atom + CISA KEV + NVD, déduplique, note chaque
élément, pousse l'important vers MARTIAN / GREEN LANTERN et génère un rapport
quotidien (et hebdomadaire) en Markdown + HTML.
"""
import calendar
import hashlib
import hmac
import html
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

# --------------------------------------------------------------------------- config
DATA = os.getenv("WATCH_DATA", "/data")
REPORTS = os.path.join(DATA, "reports")
DB = os.path.join(DATA, "watchtower.db")
CONFIG_FILE = os.getenv("WATCH_CONFIG", "/config/feeds.json")
TOKEN = os.getenv("AI_GATEWAY_TOKEN", "")
MARTIAN = os.getenv("MARTIAN_URL", "http://martian-core:8787")
NOTIFY_URL = os.getenv("GREEN_LANTERN_URL", "http://green-lantern:8898")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Paris"))


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return int(default)


FETCH_INTERVAL = env_int("WATCH_INTERVAL", 1800)
NVD_INTERVAL = env_int("WATCH_NVD_INTERVAL", 7200)
KEV_INTERVAL = env_int("WATCH_KEV_INTERVAL", 21600)
REPORT_HOUR = env_int("WATCH_REPORT_HOUR", 7)
REPORT_MINUTE = env_int("WATCH_REPORT_MINUTE", 30)
WEEKLY_DAY = env_int("WATCH_WEEKLY_DAY", 0)  # 0 = lundi
ALERT_MIN_SCORE = env_int("WATCH_ALERT_MIN_SCORE", 80)
NVD_MIN_CVSS = float(os.getenv("NVD_MIN_CVSS", "8.0"))
RETENTION_DAYS = env_int("WATCH_RETENTION_DAYS", 180)
NOTIFY_ON = os.getenv("WATCH_NOTIFY", "YES").upper() == "YES"
AI_SUMMARY = os.getenv("WATCH_AI_SUMMARY", "NO").upper() == "YES"
NVD_API_KEY = os.getenv("NVD_API_KEY", "")
UA = "Mozilla/5.0 (compatible; JusticeLeague-WATCHTOWER/1.0)"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
NVD_URL = "https://services.nvd.nist.gov/rest/json/2.0/cves"

DEFAULT_FEEDS = [
    {"name": "CERT-FR", "url": "https://www.cert.ssi.gouv.fr/feed/", "weight": 20},
    {"name": "CISA Advisories", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "weight": 20},
]

# Mots-clés de gravité : (regex, points)
SEVERITY = [
    (r"zero[- ]?day|0[- ]day", 40),
    (r"actively exploited|exploited in the wild|in the wild|exploitation active|activement exploit", 40),
    (r"\bcritical\b|\bcritique\b", 15),
    (r"\brce\b|remote code execution|ex[ée]cution de code", 25),
    (r"auth(?:entication)? bypass|contournement d.authentification", 20),
    (r"ransomware|ran[cç]ongiciel", 20),
    (r"supply[- ]chain|cha[iî]ne d.approvisionnement", 15),
    (r"data breach|fuite de donn[ée]es|\bbreach\b|\bleak(?:ed|s)?\b", 12),
    (r"\bapt\s?\d*\b|state[- ]sponsored|nation[- ]state|espionnage", 12),
    (r"backdoor|botnet|infostealer|stealer|\bmalware\b|\bwiper\b", 8),
    (r"\bpatch(?:es|ed)?\b|correctif|security update|mise [àa] jour de s[ée]curit[ée]", 3),
]
# Catégories thématiques (libellé, regex)
CATEGORIES = [
    ("Vulnérabilités", r"\bcve-\d{4}-\d{4,7}\b|vulnerab|vuln[ée]rabilit|\brce\b|zero[- ]?day|exploit"),
    ("Ransomware", r"ransomware|ran[cç]ongiciel|extortion"),
    ("APT / Espionnage", r"\bapt\s?\d*\b|state[- ]sponsored|nation[- ]state|espionnage|lazarus|sandworm|volt typhoon"),
    ("Fuites de données", r"data breach|fuite de donn[ée]es|\bbreach\b|\bleak(?:ed|s)?\b|exposed database"),
    ("Malware / Menaces", r"malware|botnet|infostealer|stealer|backdoor|trojan|loader|phishing|hameçonnage"),
    ("Supply chain", r"supply[- ]chain|cha[iî]ne d.approvisionnement|npm|pypi|package malveillant"),
    ("Correctifs", r"\bpatch(?:es|ed)?\b|correctif|security update|patch tuesday"),
]
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.I)

_db_lock = threading.Lock()
_state = {"running": set(), "started": time.time()}


# --------------------------------------------------------------------------- utils
def now_ts():
    return int(time.time())


def log(*a):
    print(datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def clean(text, n=600):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:n]


def safe_url(u):
    return u if re.match(r"^https?://", u or "", re.I) else ""


def connect():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("pragma journal_mode=wal")
    return c


def init_db():
    os.makedirs(REPORTS, exist_ok=True)
    with connect() as c:
        c.executescript(
            """
            create table if not exists items(
              id text primary key, kind text, source text, title text, link text,
              ts integer, fetched integer, summary text, category text, score integer,
              cves text, hits text, cvss real, kev integer default 0,
              alerted integer default 0, pushed integer default 0);
            create index if not exists idx_items_ts on items(ts);
            create index if not exists idx_items_score on items(score);
            create table if not exists kev(cve text primary key, vendor text, product text,
              name text, added text, due text, ransomware text);
            create table if not exists meta(k text primary key, v text);
            """
        )


def meta_get(k, default=None):
    with connect() as c:
        r = c.execute("select v from meta where k=?", (k,)).fetchone()
    return r["v"] if r else default


def meta_set(k, v):
    with _db_lock, connect() as c:
        c.execute("insert into meta(k,v) values(?,?) on conflict(k) do update set v=excluded.v", (k, str(v)))


def load_config():
    cfg = {"feeds": DEFAULT_FEEDS, "watchlist": []}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("feeds"):
            cfg["feeds"] = data["feeds"]
        cfg["watchlist"] = [w.lower() for w in data.get("watchlist", []) if w]
    except FileNotFoundError:
        log("config absente, flux par défaut utilisés:", CONFIG_FILE)
    except Exception as ex:  # JSON invalide
        log("config illisible:", ex)
    extra = [w.strip().lower() for w in os.getenv("WATCH_KEYWORDS", "").split(",") if w.strip()]
    cfg["watchlist"] = sorted(set(cfg["watchlist"] + extra))
    return cfg


# --------------------------------------------------------------------------- scoring
def analyse(title, summary, base, watchlist, cves_hint=()):
    text = f"{title} {summary}"
    low = text.lower()
    score = base
    for rx, pts in SEVERITY:
        if re.search(rx, low):
            score += pts
    cats = [name for name, rx in CATEGORIES if re.search(rx, low, re.I)]
    cves = sorted({c.upper() for c in CVE_RE.findall(text)} | {c.upper() for c in cves_hint})
    hits = [w for w in watchlist if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", low)]
    score += min(50, 25 * len(hits))
    return min(score, 100), cats, cves, hits


def add_item(c, iid, kind, source, title, link, ts, summary, base, watchlist,
             cvss=None, cves_hint=(), quiet=False, force_kev=False):
    title, summary = clean(title, 300), clean(summary, 1200)
    if not title:
        return False
    score, cats, cves, hits = analyse(title, summary, base, watchlist, cves_hint)
    kev = 1 if force_kev else 0
    if cves and not kev:
        q = ",".join("?" * len(cves))
        if c.execute(f"select 1 from kev where cve in ({q}) limit 1", cves).fetchone():
            kev, score = 1, min(100, score + 50)
    cur = c.execute(
        "insert or ignore into items(id,kind,source,title,link,ts,fetched,summary,category,score,"
        "cves,hits,cvss,kev,alerted) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (iid, kind, source, title, safe_url(link), ts, now_ts(), summary,
         ",".join(cats), score, ",".join(cves), ",".join(hits), cvss, kev, 1 if quiet else 0),
    )
    return cur.rowcount > 0


# --------------------------------------------------------------------------- collecte
def http_get(url, **kw):
    r = httpx.get(url, headers={"User-Agent": UA, **kw.pop("headers", {})}, timeout=25,
                  follow_redirects=True, **kw)
    r.raise_for_status()
    if len(r.content) > 8_000_000:
        raise ValueError("réponse trop volumineuse")
    return r


def is_quiet():
    return meta_get("bootstrapped") is None


def run_fetch():
    cfg = load_config()
    quiet = is_quiet()
    status, new_total = {}, 0
    cutoff = now_ts() - RETENTION_DAYS * 86400
    for feed in cfg["feeds"]:
        name, url, weight = feed.get("name", feed["url"]), feed["url"], int(feed.get("weight", 10))
        try:
            parsed = feedparser.parse(http_get(url).content)
            if parsed.bozo and not parsed.entries:
                raise ValueError(str(parsed.bozo_exception)[:120])
            n = 0
            with _db_lock, connect() as c:
                for e in parsed.entries[:60]:
                    t = e.get("published_parsed") or e.get("updated_parsed")
                    ts = calendar.timegm(t) if t else now_ts()
                    if ts < cutoff:
                        continue
                    link, title = e.get("link", ""), e.get("title", "")
                    iid = "rss:" + hashlib.sha256((link or title).encode()).hexdigest()[:32]
                    summary = e.get("summary") or e.get("description") or ""
                    if add_item(c, iid, "news", name, title, link, min(ts, now_ts()), summary,
                                weight, cfg["watchlist"], quiet=quiet):
                        n += 1
            status[name] = {"ok": True, "new": n, "at": now_ts()}
            new_total += n
        except Exception as ex:
            status[name] = {"ok": False, "error": str(ex).splitlines()[0][:160], "at": now_ts()}
            log("flux en erreur", name, ex)
    meta_set("feed_status", json.dumps(status))
    meta_set("last_fetch", now_ts())
    log(f"fetch terminé: {new_total} nouveaux éléments")
    return new_total


def run_kev():
    quiet = is_quiet()
    data = http_get(KEV_URL).json()
    cfg = load_config()
    new = 0
    horizon = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    with _db_lock, connect() as c:
        for v in data.get("vulnerabilities", []):
            cve = v["cveID"].upper()
            c.execute("insert or ignore into kev values(?,?,?,?,?,?,?)",
                      (cve, v.get("vendorProject"), v.get("product"), v.get("vulnerabilityName"),
                       v.get("dateAdded"), v.get("dueDate"), v.get("knownRansomwareCampaignUse")))
            # élément visible uniquement pour les ajouts récents
            if (v.get("dateAdded") or "") >= horizon:
                try:
                    ts = int(datetime.strptime(v["dateAdded"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
                except Exception:
                    ts = now_ts()
                ransom = " Utilisée dans des campagnes ransomware." if v.get("knownRansomwareCampaignUse") == "Known" else ""
                title = f"[CISA KEV] {cve} — {v.get('vendorProject')} {v.get('product')} : {v.get('vulnerabilityName')}"
                summary = f"{v.get('shortDescription', '')} Échéance de remédiation CISA : {v.get('dueDate')}.{ransom}"
                if add_item(c, "kev:" + cve, "kev", "CISA KEV", title,
                            f"https://nvd.nist.gov/vuln/detail/{cve}", ts, summary, 70,
                            cfg["watchlist"], cves_hint=[cve], quiet=quiet, force_kev=True):
                    new += 1
        # rescore des articles déjà connus qui mentionnent une CVE désormais dans la KEV
        c.execute(
            "update items set kev=1, score=min(100,score+50), alerted=case when ?=1 then 1 else alerted end "
            "where kev=0 and kind!='kev' and exists("
            "select 1 from kev k where instr(','||items.cves||',', ','||k.cve||',')>0)", (1 if quiet else 0,))
    meta_set("last_kev", now_ts())
    log(f"KEV terminé: {new} nouvelles entrées")
    return new


def run_nvd():
    cfg = load_config()
    quiet = is_quiet()
    end = datetime.now(timezone.utc)
    last = meta_get("nvd_last")
    start = datetime.fromtimestamp(int(last), timezone.utc) if last else end - timedelta(hours=24)
    start = max(start, end - timedelta(days=100))
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000")
    headers = {"apiKey": NVD_API_KEY} if NVD_API_KEY else {}
    idx, new = 0, 0
    for _ in range(6):
        r = http_get(NVD_URL, headers=headers, params={
            "pubStartDate": fmt(start), "pubEndDate": fmt(end), "resultsPerPage": 2000, "startIndex": idx})
        data = r.json()
        vulns = data.get("vulnerabilities", [])
        with _db_lock, connect() as c:
            for v in vulns:
                cve = v["cve"]
                cid = cve["id"].upper()
                desc = next((d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"), "")
                if desc.startswith("** REJECT"):
                    continue
                cvss = None
                for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    if cve.get("metrics", {}).get(key):
                        cvss = cve["metrics"][key][0]["cvssData"].get("baseScore")
                        break
                low = desc.lower()
                watch = any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", low) for w in cfg["watchlist"])
                if not ((cvss or 0) >= NVD_MIN_CVSS or watch):
                    continue
                base = 60 if (cvss or 0) >= 9 else 45 if (cvss or 0) >= 8 else 30 if (cvss or 0) >= 7 else 15
                try:
                    ts = int(datetime.fromisoformat(cve["published"]).replace(tzinfo=timezone.utc).timestamp())
                except Exception:
                    ts = now_ts()
                title = f"{cid} (CVSS {cvss if cvss is not None else 'n/a'}) — {clean(desc, 120)}"
                if add_item(c, "nvd:" + cid, "cve", "NVD", title,
                            f"https://nvd.nist.gov/vuln/detail/{cid}", ts, desc, base,
                            cfg["watchlist"], cvss=cvss, cves_hint=[cid], quiet=quiet):
                    new += 1
        idx += len(vulns)
        if not vulns or idx >= data.get("totalResults", 0):
            break
    meta_set("nvd_last", int(end.timestamp()))
    meta_set("last_nvd", now_ts())
    log(f"NVD terminé: {new} nouvelles CVE retenues")
    return new


# --------------------------------------------------------------------------- push / alertes
def push_martian():
    with connect() as c:
        rows = c.execute("select * from items where pushed=0 and (score>=50 or kind in ('kev','cve')) "
                         "order by ts desc limit 200").fetchall()
    ok = 0
    for r in rows:
        data = {k: r[k] for k in ("kind", "source", "title", "link", "ts", "summary", "category",
                                  "score", "cves", "hits", "cvss", "kev")}
        try:
            resp = httpx.post(MARTIAN + "/memory/entity", headers={"X-AI-Gateway-Token": TOKEN},
                              json={"entity_type": "veille", "external_id": r["id"], "data": data}, timeout=10)
            resp.raise_for_status()
            with _db_lock, connect() as c:
                c.execute("update items set pushed=1 where id=?", (r["id"],))
            ok += 1
        except Exception as ex:
            log("MARTIAN indisponible, nouvel essai au prochain cycle:", ex)
            break
    return ok


def notify(title, body, severity="info"):
    if not NOTIFY_ON:
        return False
    try:
        httpx.post(NOTIFY_URL + "/notify", json={"title": title, "body": body[:1700], "severity": severity},
                   timeout=15).raise_for_status()
        return True
    except Exception as ex:
        log("GREEN LANTERN indisponible:", ex)
        return False


def send_alerts():
    with connect() as c:
        rows = c.execute("select * from items where alerted=0 and score>=? order by score desc, ts desc limit 8",
                         (ALERT_MIN_SCORE,)).fetchall()
    if not rows:
        return 0
    lines = [f"• [{r['score']}] {r['title'][:140]} ({r['source']}) {r['link']}" for r in rows]
    if notify("WATCHTOWER — alerte veille cyber", "\n".join(lines), "high"):
        with _db_lock, connect() as c:
            c.executemany("update items set alerted=1 where id=?", [(r["id"],) for r in rows])
        return len(rows)
    return 0


# --------------------------------------------------------------------------- rapports
def ai_summary(items):
    if not AI_SUMMARY or not items:
        return None
    bullets = "\n".join(f"- {i['title']} ({i['source']})" for i in items[:15])
    prompt = ("Tu es analyste CTI. À partir UNIQUEMENT des éléments ci-dessous, rédige en français une synthèse "
              "de 5 puces maximum des faits marquants et de ce qu'il faut traiter en priorité. "
              "N'invente aucun détail absent de la liste.\n\n" + bullets)
    try:
        r = httpx.post(OLLAMA_URL + "/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                       timeout=240)
        r.raise_for_status()
        return clean(r.json().get("response", ""), 2500) or None
    except Exception as ex:
        log("synthèse IA indisponible:", ex)
        return None


def collect_report(period):
    hours = 24 if period == "daily" else 168
    since = now_ts() - hours * 3600
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "select * from items where ts>=? order by score desc, ts desc", (since,)).fetchall()]
    by_cat = {}
    for r in rows:
        for cat in (r["category"] or "Autres").split(","):
            by_cat.setdefault(cat or "Autres", []).append(r)
    cve_count = {}
    for r in rows:
        for cve in filter(None, (r["cves"] or "").split(",")):
            cve_count.setdefault(cve, []).append(r)
    trending = sorted(((k, v) for k, v in cve_count.items() if len(v) >= 2), key=lambda x: -len(x[1]))[:10]
    return {
        "period": period, "hours": hours, "rows": rows,
        "priority": [r for r in rows if r["score"] >= 70][:10],
        "kev": [r for r in rows if r["kind"] == "kev"][:20],
        "cves": sorted([r for r in rows if r["kind"] == "cve"], key=lambda r: -(r["cvss"] or 0))[:15],
        "watch": [r for r in rows if r["hits"]][:15],
        "by_cat": {k: v[:8] for k, v in sorted(by_cat.items(), key=lambda kv: -len(kv[1]))},
        "cat_counts": {k: len(v) for k, v in by_cat.items()},
        "trending": [(k, len(v), v[0]["link"]) for k, v in trending],
        "sources": len({r["source"] for r in rows}),
    }


def fmt_date(ts):
    return datetime.fromtimestamp(ts, TZ).strftime("%d/%m %H:%M")


def md_item(r, detail=False):
    title = r["title"].replace("[", "(").replace("]", ")")
    tags = " · ".join(x for x in [r["category"].replace(",", ", ") if r["category"] else "", r["cves"].replace(",", ", ")
                                  if r["cves"] and r["kind"] == "news" else ""] if x)
    link = f"[{title}]({r['link']})" if r["link"] else title
    line = f"- **{r['score']}** {link} — {r['source']} · {fmt_date(r['ts'])}" + (f" · {tags}" if tags else "")
    if r["kev"] and r["kind"] != "kev":
        line += " · ⚠️ KEV"
    if detail and r["summary"]:
        line += f"\n  > {r['summary'][:260]}"
    return line


def render_md(rep, ai):
    label = "quotidien" if rep["period"] == "daily" else "hebdomadaire"
    now = datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    out = [f"# Rapport de veille cyber {label} — {datetime.now(TZ).strftime('%d/%m/%Y')}",
           f"_Généré le {now} par WATCHTOWER — fenêtre : {rep['hours']} h_", "",
           "## Chiffres clés",
           f"- {len(rep['rows'])} éléments analysés, issus de {rep['sources']} sources",
           f"- {len(rep['kev'])} ajout(s) CISA KEV (vulnérabilités exploitées activement)",
           f"- {len(rep['cves'])} CVE à fort score retenue(s) (CVSS ≥ {NVD_MIN_CVSS:g} ou watchlist)",
           f"- {len(rep['priority'])} élément(s) prioritaire(s) (score ≥ 70)"]
    if rep["cat_counts"]:
        out.append("- Répartition : " + ", ".join(f"{k} ({v})" for k, v in
                                                  sorted(rep["cat_counts"].items(), key=lambda kv: -kv[1])))
    if ai:
        out += ["", "## Synthèse IA (générée localement, à vérifier)", ai]
    if rep["priority"]:
        out += ["", "## À traiter en priorité"] + [md_item(r, True) for r in rep["priority"]]
    if rep["kev"]:
        out += ["", "## Nouvelles entrées CISA KEV"] + [md_item(r) for r in rep["kev"]]
    if rep["watch"]:
        out += ["", "## Concerne votre périmètre (watchlist)"] + [
            md_item(r) + f" · mots-clés : {r['hits']}" for r in rep["watch"]]
    if rep["cves"]:
        out += ["", "## CVE à fort score", "| CVE | CVSS | Description |", "|---|---|---|"]
        for r in rep["cves"]:
            cve = (r["cves"] or "").split(",")[0]
            out.append(f"| [{cve}]({r['link']}) | {r['cvss'] if r['cvss'] is not None else 'n/a'} | "
                       f"{(r['summary'] or '')[:140].replace('|', '/')} |")
    if rep["trending"]:
        out += ["", "## CVE les plus citées"] + [f"- [{c}]({lnk}) — citée {n} fois" for c, n, lnk in rep["trending"]]
    if rep["by_cat"]:
        out += ["", "## Par thème"]
        for cat, items in rep["by_cat"].items():
            out += [f"### {cat} ({rep['cat_counts'][cat]})"] + [md_item(r) for r in items]
    out += ["", "---", "_Les scores sont heuristiques (mots-clés, KEV, CVSS, watchlist) : ils aident à trier, "
            "ils ne remplacent pas une analyse._"]
    return "\n".join(out) + "\n"


def render_html(rep, ai):
    e = html.escape

    def li(r, detail=False):
        link = f'<a href="{e(r["link"])}" rel="noopener noreferrer">{e(r["title"])}</a>' if r["link"] else e(r["title"])
        bits = [e(r["source"]), fmt_date(r["ts"])]
        if r["category"]:
            bits.append(e(r["category"].replace(",", ", ")))
        if r["kev"]:
            bits.append("<b>KEV</b>")
        s = f'<li><span class="s s{min(r["score"] // 25, 3)}">{r["score"]}</span> {link}<br><small>{" · ".join(bits)}</small>'
        if detail and r["summary"]:
            s += f'<br><small class="d">{e(r["summary"][:260])}</small>'
        return s + "</li>"

    def sec(title, items, detail=False):
        return f"<h2>{e(title)}</h2><ul>{''.join(li(r, detail) for r in items)}</ul>" if items else ""

    label = "quotidien" if rep["period"] == "daily" else "hebdomadaire"
    parts = [f"<h1>Rapport de veille cyber {label} — {datetime.now(TZ).strftime('%d/%m/%Y')}</h1>",
             f'<p class="m">Généré le {datetime.now(TZ).strftime("%d/%m/%Y %H:%M")} · fenêtre {rep["hours"]} h</p>',
             '<div class="k">'
             f'<div><b>{len(rep["rows"])}</b>éléments</div><div><b>{rep["sources"]}</b>sources</div>'
             f'<div><b>{len(rep["kev"])}</b>KEV</div><div><b>{len(rep["cves"])}</b>CVE fort score</div>'
             f'<div><b>{len(rep["priority"])}</b>prioritaires</div></div>']
    if ai:
        parts.append(f"<h2>Synthèse IA <small>(locale, à vérifier)</small></h2><p>{e(ai).replace(chr(10), '<br>')}</p>")
    parts.append(sec("À traiter en priorité", rep["priority"], True))
    parts.append(sec("Nouvelles entrées CISA KEV", rep["kev"]))
    parts.append(sec("Concerne votre périmètre (watchlist)", rep["watch"]))
    if rep["cves"]:
        rows = "".join(f'<tr><td><a href="{e(r["link"])}">{e((r["cves"] or "").split(",")[0])}</a></td>'
                       f'<td>{e(str(r["cvss"]) if r["cvss"] is not None else "n/a")}</td>'
                       f'<td>{e((r["summary"] or "")[:160])}</td></tr>' for r in rep["cves"])
        parts.append(f'<h2>CVE à fort score</h2><div class="w"><table><tr><th>CVE</th><th>CVSS</th><th>Description</th></tr>{rows}</table></div>')
    if rep["trending"]:
        parts.append("<h2>CVE les plus citées</h2><ul>" + "".join(
            f'<li><a href="{e(l)}">{e(c)}</a> — {n} mentions</li>' for c, n, l in rep["trending"]) + "</ul>")
    for cat, items in rep["by_cat"].items():
        parts.append(sec(f"{cat} ({rep['cat_counts'][cat]})", items))
    css = ("<style>:root{--bg:#fff;--fg:#1a1d23;--mu:#5b6270;--bd:#d9dde3;--ac:#0b5fff;--c0:#e8ebf0;--c1:#fff1b8;--c2:#ffd1a1;--c3:#ffb3b3}"
           "@media(prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e8eaee;--mu:#9aa2b1;--bd:#2c313a;--ac:#6ea0ff;--c0:#262a31;--c1:#4a4220;--c2:#573a1c;--c3:#5c2424}}"
           "body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:900px;margin:0 auto;padding:24px 16px}"
           "a{color:var(--ac)}h1{font-size:1.5rem}h2{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid var(--bd);padding-bottom:4px}"
           "ul{padding-left:0;list-style:none}li{margin:10px 0}small,.m{color:var(--mu)}.d{display:block}"
           ".s{display:inline-block;min-width:2.2em;text-align:center;border-radius:4px;font-weight:700;font-size:.8rem;padding:1px 4px}"
           ".s0{background:var(--c0)}.s1{background:var(--c1)}.s2{background:var(--c2)}.s3{background:var(--c3)}"
           ".k{display:flex;flex-wrap:wrap;gap:10px}.k div{border:1px solid var(--bd);border-radius:8px;padding:8px 14px;text-align:center}.k b{display:block;font-size:1.4rem}"
           ".w{overflow-x:auto}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--bd);padding:6px 8px;text-align:left;font-size:.9rem}</style>")
    foot = '<p class="m">Scores heuristiques (mots-clés, KEV, CVSS, watchlist) : ils aident à trier, sans remplacer une analyse.</p>'
    return ("<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Veille cyber {label}</title>{css}</head><body>{''.join(parts)}{foot}</body></html>")


def run_report(period):
    rep = collect_report(period)
    ai = ai_summary(rep["rows"]) if period == "daily" or AI_SUMMARY else None
    stamp = datetime.now(TZ).strftime("%Y-%m-%d")
    base = os.path.join(REPORTS, f"{stamp}-{period}")
    for ext, content in (("md", render_md(rep, ai)), ("html", render_html(rep, ai))):
        tmp = f"{base}.{ext}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, f"{base}.{ext}")
    meta_set(f"last_{period}", stamp if period == "daily" else datetime.now(TZ).strftime("%G-W%V"))
    top = rep["priority"][:5]
    body = f"{len(rep['rows'])} éléments, {len(rep['kev'])} KEV, {len(rep['priority'])} prioritaires.\n" + "\n".join(
        f"• [{r['score']}] {r['title'][:120]}" for r in top)
    notify(f"WATCHTOWER — rapport {period} disponible ({stamp})", body, "info")
    log(f"rapport {period} généré: {base}.md/.html")
    return base


def cleanup():
    cutoff = now_ts() - RETENTION_DAYS * 86400
    with _db_lock, connect() as c:
        c.execute("delete from items where ts<?", (cutoff,))


# --------------------------------------------------------------------------- planificateur
TASKS = {"fetch": run_fetch, "nvd": run_nvd, "kev": run_kev,
         "daily": lambda: run_report("daily"), "weekly": lambda: run_report("weekly")}


def run_task(name):
    if name in _state["running"]:
        return
    _state["running"].add(name)
    try:
        TASKS[name]()
    except Exception as ex:
        log(f"tâche {name} en échec:", ex)
        meta_set(f"error_{name}", f"{datetime.now(TZ).isoformat()} {str(ex)[:200]}")
    finally:
        _state["running"].discard(name)


def due(key, interval):
    return now_ts() - int(meta_get(key, 0) or 0) >= interval


def scheduler():
    time.sleep(3)
    while True:
        try:
            if due("last_kev", KEV_INTERVAL):
                run_task("kev")
            if due("last_fetch", FETCH_INTERVAL):
                run_task("fetch")
            if due("last_nvd", NVD_INTERVAL):
                run_task("nvd")
            if is_quiet() and any(f.get("ok") for f in json.loads(meta_get("feed_status", "{}")).values()):
                meta_set("bootstrapped", now_ts())  # premier cycle réussi : fin du mode silencieux
            push_martian()
            send_alerts()
            n = datetime.now(TZ)
            after = (n.hour, n.minute) >= (REPORT_HOUR, REPORT_MINUTE)
            if after and meta_get("last_daily") != n.strftime("%Y-%m-%d") and meta_get("last_fetch"):
                run_task("daily")
                cleanup()
            if (after and n.weekday() == WEEKLY_DAY and meta_get("last_weekly") != n.strftime("%G-W%V")
                    and meta_get("last_fetch")):
                run_task("weekly")
        except Exception as ex:
            log("erreur planificateur:", ex)
        time.sleep(30)


@asynccontextmanager
async def lifespan(_):
    init_db()
    threading.Thread(target=scheduler, daemon=True, name="scheduler").start()
    log("WATCHTOWER démarré")
    yield


# --------------------------------------------------------------------------- API / UI
app = FastAPI(title="WATCHTOWER", version="1.0.0", lifespan=lifespan)
NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(daily|weekly)\.(md|html)$")


def require_token(tok):
    if not TOKEN:
        raise HTTPException(503, "AI_GATEWAY_TOKEN non configuré")
    if not tok or not hmac.compare_digest(tok, TOKEN):
        raise HTTPException(401, "token invalide")


@app.get("/health")
def health():
    with connect() as c:
        total = c.execute("select count(*) n from items").fetchone()["n"]
    feeds = json.loads(meta_get("feed_status", "{}"))
    return {"status": "ok", "service": "WATCHTOWER", "items": total,
            "last_fetch": meta_get("last_fetch"), "last_daily": meta_get("last_daily"),
            "feeds_ok": sum(1 for f in feeds.values() if f.get("ok")), "feeds_total": len(feeds),
            "feeds_errors": {k: v["error"] for k, v in feeds.items() if not v.get("ok")}}


@app.get("/items")
def items(hours: int = 24, min_score: int = 0, q: str = "", limit: int = 100):
    limit = max(1, min(limit, 500))
    like = f"%{q.lower()}%"
    with connect() as c:
        rows = c.execute(
            "select id,kind,source,title,link,ts,category,score,cves,hits,cvss,kev from items "
            "where ts>=? and score>=? and (?='' or lower(title||' '||summary) like ?) "
            "order by score desc, ts desc limit ?",
            (now_ts() - max(1, hours) * 3600, min_score, q, like, limit)).fetchall()
    return [dict(r) for r in rows]


@app.get("/reports")
def reports():
    return sorted((f for f in os.listdir(REPORTS) if NAME_RE.match(f)), reverse=True)


@app.get("/reports/{name}")
def report(name: str):
    if not NAME_RE.match(name):
        raise HTTPException(404)
    path = os.path.join(REPORTS, name)
    if not os.path.isfile(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="text/html; charset=utf-8" if name.endswith(".html")
                        else "text/markdown; charset=utf-8")


@app.post("/run/{task}")
def run(task: str, x_ai_gateway_token: str | None = Header(default=None)):
    require_token(x_ai_gateway_token)
    if task not in TASKS:
        raise HTTPException(404, "tâches: " + ", ".join(TASKS))
    threading.Thread(target=run_task, args=(task,), daemon=True).start()
    return {"started": task}


@app.get("/", response_class=HTMLResponse)
def home():
    e = html.escape
    top = items(hours=24, min_score=40, limit=25)
    reps = reports()
    rows = "".join(
        f'<li><b>{r["score"]}</b> <a href="{e(r["link"])}" rel="noopener noreferrer">{e(r["title"])}</a> '
        f'<small>— {e(r["source"])} · {fmt_date(r["ts"])}</small></li>' for r in top) or "<li>Aucun élément pour l'instant.</li>"
    rl = "".join(f'<li><a href="/reports/{e(n)}">{e(n)}</a></li>' for n in reps if n.endswith(".html")) or "<li>Aucun rapport.</li>"
    return HTMLResponse(
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>WATCHTOWER</title><style>:root{color-scheme:light dark}body{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:24px 16px}"
        "li{margin:6px 0}ul{padding-left:18px}small{opacity:.7}</style></head><body><h1>WATCHTOWER — veille cyber</h1>"
        f"<h2>Rapports</h2><ul>{rl}</ul><h2>À surveiller (24 h, score ≥ 40)</h2><ul>{rows}</ul>"
        "<p><small><a href='/health'>état</a> · <a href='/items'>API items</a></small></p></body></html>")
