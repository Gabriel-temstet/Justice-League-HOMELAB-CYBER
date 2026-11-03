#!/usr/bin/env python3
"""ORACLE — module « prophéties ».

Transforme ce qu'ORACLE sait (CVE/EPSS/KEV + dérives OSINT) et ce que GREEN ARROW a
mesuré (inventaire services/versions) en prophéties publiées dans MARTIAN :

    « CVE-X sera probablement exploitée sur l'actif Y avant la date D »  (basis=model)
    « le certificat de example.fr expire dans 5 jours »                  (basis=rule)

Principes :
- la probabilité vient de données publiques (EPSS de FIRST, CISA KEV), jamais du LLM ;
- le croisement CVE <-> actif passe par le CPE relevé par nmap -sV : pas de CPE, pas de prophétie
  (on préfère rater un cas que fabriquer un faux positif) ;
- ORACLE ne scanne rien et ne corrige rien : il publie, GREEN ARROW vérifie, un humain décide.

Deux boucles : `cycle()` (toutes les PROPHET_INTERVAL s) calcule et publie ;
`dispatch()` (toutes les 60 s) prévient GREEN LANTERN quand une prophétie le mérite.
"""
import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

MARTIAN = os.getenv("MARTIAN_URL", "http://martian-core:8787")
GREEN_LANTERN = os.getenv("GREEN_LANTERN_URL", "http://green-lantern:8898")
TOKEN = os.getenv("AI_GATEWAY_TOKEN", "")
NVD_API_KEY = os.getenv("NVD_API_KEY", "")
ENABLED = os.getenv("PROPHET_ENABLED", "YES").upper() == "YES"
NOTIFY = os.getenv("PROPHET_NOTIFY", "YES").upper() == "YES"


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return int(default)


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


INTERVAL = _int("PROPHET_INTERVAL", 3600)
MIN_PRIORITY = _float("PROPHET_MIN_PRIORITY", 5)        # sous ce seuil : non publiée (sauf KEV)
NOTIFY_MIN = _float("PROPHET_NOTIFY_MIN", 50)           # seuil de notification humaine
VERIFY_TIMEOUT_H = _float("PROPHET_VERIFY_TIMEOUT_H", 2)  # attente de la vérification GREEN ARROW
NVD_CACHE_H = _float("PROPHET_NVD_CACHE_H", 24)
HOME = Path(os.getenv("HOME", "/data/home"))
OSINT_STATE = HOME / "veille-osint" / "etat.json"
DB = os.getenv("PROPHET_DB", "/data/prophet.db")
NVD_URL = "https://services.nvd.nist.gov/rest/json/2.0/cves"
EPSS_URL = "https://api.first.org/data/v1/epss"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
UA = "JusticeLeague-ORACLE/1.0"
HDR = {"X-AI-Gateway-Token": TOKEN}

try:  # criticité par actif : {"10.0.0.5": 2.0} (1.0 par défaut, borné 0.1-3)
    CRIT = {k: max(0.1, min(3.0, float(v))) for k, v in json.loads(os.getenv("ASSET_CRITICALITY", "{}") or "{}").items()}
except Exception:
    CRIT = {}


def log(*a):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "[prophet]", *a, flush=True)


# ----------------------------------------------------------------------------- calculs purs
def cpe_to_23(cpe):
    """CPE 2.2 URI (sortie de nmap) -> CPE 2.3 tel que NVD l'indexe, ou None sans version.
    Garder IDENTIQUE à green-arrow/inventory.py : GREEN ARROW compare les CPE produits par les deux."""
    if not cpe:
        return None
    if cpe.startswith("cpe:2.3:"):
        parts = cpe.split(":")
        return cpe if len(parts) >= 6 and parts[5] not in ("", "*", "-") else None
    if not cpe.startswith("cpe:/"):
        return None
    f = cpe[5:].split(":")
    if len(f) < 4 or not f[3] or f[0] not in "aoh":
        return None
    part, vendor, product, version = f[:4]
    update = f[4] if len(f) > 4 and f[4] else "*"
    # NVD indexe OpenSSH « 8.4p1 » en version 8.4 + update p1
    m = re.fullmatch(r"(\d+(?:\.\d+)+)(p\d+)", version) if (vendor, product) == ("openbsd", "openssh") else None
    if m:
        version, update = m.group(1), m.group(2)
    return f"cpe:2.3:{part}:{vendor}:{product}:{version}:{update}:*:*:*:*:*:*"


def probability(epss, kev):
    """P(exploitation) : EPSS, relevé à 0.95 si la CVE est dans la CISA KEV (exploitation avérée)."""
    p = float(epss or 0.0)
    return max(p, 0.95) if kev else p


def priority(p, asset):
    return round(min(100.0, 100.0 * p * CRIT.get(asset, 1.0)), 2)


def deadline_for(p, kev_due=None, now=None):
    now = now or datetime.now(timezone.utc)
    if kev_due:
        try:
            return datetime.strptime(kev_due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return now + timedelta(days=7 if p >= 0.5 else 30)


# ----------------------------------------------------------------------------- MARTIAN
def martian(method, path, **kw):
    r = httpx.request(method, MARTIAN + path, headers=HDR, timeout=20, **kw)
    r.raise_for_status()
    return r.json()


# ----------------------------------------------------------------------------- sources publiques
def _cache():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("create table if not exists nvd_cache(cpe text primary key, ts integer, cves text)")
    return c


def nvd_cves_for(cpe23, cache):
    """CVE affectant ce CPE précis (NVD, avec cache). Retourne None en cas d'échec transitoire."""
    row = cache.execute("select ts,cves from nvd_cache where cpe=?", (cpe23,)).fetchone()
    if row and time.time() - row[0] < NVD_CACHE_H * 3600:
        return json.loads(row[1])
    time.sleep(0.7 if NVD_API_KEY else 6.5)  # quota NVD : 50 req/30 s avec clé, 5 sans
    headers = {"User-Agent": UA, **({"apiKey": NVD_API_KEY} if NVD_API_KEY else {})}
    out, idx = [], 0
    while True:
        r = httpx.get(NVD_URL, headers=headers, timeout=40,
                      params={"cpeName": cpe23, "isVulnerable": "", "resultsPerPage": 500, "startIndex": idx})
        if r.status_code in (400, 404):      # CPE inconnu de NVD : résultat vide légitime
            log("CPE inconnu de NVD (aucune CVE) :", cpe23)
            out = []
            break
        if r.status_code != 200:
            log("NVD indisponible", r.status_code, cpe23)
            return None
        data = r.json()
        for v in data.get("vulnerabilities", []):
            cve = v["cve"]
            desc = next((d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"), "")
            if desc.startswith("** REJECT"):
                continue
            cvss = None
            for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if cve.get("metrics", {}).get(key):
                    cvss = cve["metrics"][key][0]["cvssData"].get("baseScore")
                    break
            out.append({"id": cve["id"].upper(), "cvss": cvss, "desc": desc[:200]})
        idx += len(data.get("vulnerabilities", []))
        if not data.get("vulnerabilities") or idx >= data.get("totalResults", 0):
            break
    cache.execute("insert or replace into nvd_cache values(?,?,?)", (cpe23, int(time.time()), json.dumps(out)))
    cache.commit()
    return out


def fetch_epss(cves):
    out = {}
    cves = sorted(set(cves))
    for i in range(0, len(cves), 50):
        r = httpx.get(EPSS_URL, params={"cve": ",".join(cves[i:i + 50])}, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        for d in r.json().get("data", []):
            out[d["cve"].upper()] = (float(d["epss"]), float(d.get("percentile", 0)))
    return out


def fetch_kev():
    r = httpx.get(KEV_URL, headers={"User-Agent": UA}, timeout=40, follow_redirects=True)
    r.raise_for_status()
    return {v["cveID"].upper(): {"due": v.get("dueDate"), "ransomware": v.get("knownRansomwareCampaignUse")}
            for v in r.json().get("vulnerabilities", [])}


# ----------------------------------------------------------------------------- prophéties CVE
def cve_prophecies(inventory, nvd=nvd_cves_for, epss_fn=fetch_epss, kev_fn=fetch_kev):
    """Retourne (prophéties, actifs_vus, actifs_en_erreur)."""
    cache = _cache()
    found = []   # (asset, svc, cpe23, cve_dict)
    seen, failed = set(), set()
    for a in inventory:
        asset = a["asset"]
        seen.add(asset)
        for svc in a.get("services", []):
            cpe23 = next(filter(None, (cpe_to_23(c) for c in svc.get("cpe", []))), None)
            if not cpe23:
                continue
            cves = nvd(cpe23, cache)
            if cves is None:
                failed.add(asset)
                continue
            for c in cves:
                found.append((asset, svc, cpe23, c))
    if not found:
        return [], seen, failed
    epss, kev = {}, {}
    try:
        epss = epss_fn([f[3]["id"] for f in found])
    except Exception as ex:
        log("EPSS indisponible (priorité calculée sans):", ex)
    try:
        kev = kev_fn()
    except Exception as ex:
        log("KEV indisponible:", ex)
    out = []
    for asset, svc, cpe23, c in found:
        cid = c["id"]
        e, pct = epss.get(cid, (None, None))
        k = kev.get(cid)
        p = probability(e, bool(k))
        prio = priority(p, asset)
        if prio < MIN_PRIORITY and not k:
            continue
        port = svc.get("port")
        label = f"{svc.get('product') or svc.get('name') or '?'} {svc.get('version') or ''}".strip()
        out.append({
            "key": f"cve:{cid}@{asset}:{port}", "kind": "cve", "cve": cid, "asset": asset, "port": port,
            "title": f"{cid} sur {asset}:{port} ({label})" + (" — exploitée (CISA KEV)" if k else ""),
            "probability": round(p, 4), "priority": prio, "basis": "model",
            "deadline": deadline_for(p, k["due"] if k else None).isoformat(),
            "rationale": {"epss": e, "epss_percentile": pct, "kev": bool(k),
                          "kev_ransomware": (k or {}).get("ransomware"), "cvss": c.get("cvss"),
                          "cpe": cpe23, "service": label, "criticality": CRIT.get(asset, 1.0),
                          "summary": c.get("desc"), "formula": "priority = 100 × P × criticité ; P = max(EPSS, 0.95 si KEV)"},
        })
    return out, seen, failed


# ----------------------------------------------------------------------------- visions OSINT
def osint_prophecies(state):
    """Règles déterministes sur l'état OSINT (osint_veille.py). basis=rule : ce ne sont pas des probabilités."""
    out = []
    for dom, s in state.items():
        tls = s.get("tls", {})
        if "jours" in tls and tls["jours"] <= 30:
            p = 0.95 if tls["jours"] <= 7 else 0.6
            out.append({"key": f"osint:tls-expiry@{dom}", "kind": "osint", "asset": dom,
                        "title": f"Certificat TLS de {dom} : expiration dans {tls['jours']} j",
                        "probability": p, "priority": round(p * 100, 2), "basis": "rule",
                        "deadline": (datetime.strptime(tls["expire"], "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
                                     if tls.get("expire") else None),
                        "rationale": {"expire": tls.get("expire"), "emetteur": tls.get("emetteur"), "rule": "TLS ≤ 30 j (0.95 si ≤ 7 j)"}})
        m = re.search(r"\bp=(\w+)", s.get("dmarc") or "")
        if not m or m.group(1).lower() == "none":
            out.append({"key": f"osint:dmarc@{dom}", "kind": "osint", "asset": dom,
                        "title": f"{dom} : DMARC absent ou p=none (usurpation mail possible)",
                        "probability": 0.3, "priority": 30, "basis": "rule", "deadline": None,
                        "rationale": {"dmarc": s.get("dmarc") or None, "rule": "DMARC absent ou p=none"}})
        if not s.get("spf"):
            out.append({"key": f"osint:spf@{dom}", "kind": "osint", "asset": dom,
                        "title": f"{dom} : SPF absent", "probability": 0.3, "priority": 30, "basis": "rule",
                        "deadline": None, "rationale": {"rule": "SPF absent"}})
    return out


def load_osint():
    try:
        return json.loads(OSINT_STATE.read_text())
    except Exception:
        return {}


# ----------------------------------------------------------------------------- cycle principal
def cycle():
    inv = martian("GET", "/inventory").get("assets", [])
    cve_p, seen, failed = cve_prophecies(inv)
    state = load_osint()
    osint_p = osint_prophecies(state)
    produced = {p["key"] for p in cve_p + osint_p}
    new = 0
    for p in cve_p + osint_p:
        try:
            if martian("POST", "/prophecies", json=p).get("created"):
                new += 1
        except Exception as ex:
            log("publication impossible:", p["key"], ex)
    # prophéties devenues caduques : actif réinventorié (sans erreur NVD) et risque disparu
    live = martian("GET", "/prophecies", params={"status": "open,confirmed,notified,acknowledged", "limit": 1000})["prophecies"]
    resolved = 0
    for p in live:
        if p["key"] in produced:
            continue
        gone = ((p["kind"] == "cve" and p["asset"] in seen and p["asset"] not in failed) or
                (p["kind"] == "osint" and p["asset"] in state))
        if gone:
            martian("PATCH", f"/prophecies/{p['id']}", json={"status": "resolved", "evidence": {
                "by": "ORACLE", "reason": "risque non reproduit au dernier cycle"}})
            resolved += 1
    log(f"cycle: {len(inv)} actifs, {new} nouvelles prophéties, {len(produced)} actives, {resolved} résolues")


def notify_text(p):
    r = p.get("rationale") or {}
    lines = [p["title"], f"Probabilité {float(p['probability']):.0%} · priorité {float(p['priority']):.0f}/100"
             + (f" · échéance {p['deadline'][:10]}" if p.get("deadline") else "")]
    if r.get("epss") is not None:
        lines.append(f"EPSS {r['epss']:.3f} · CVSS {r.get('cvss')}")
    lines.append({"confirmed": "✔ Vérifiée par GREEN ARROW (service exposé confirmé)",
                  "open": "⚠ Non vérifiée (hors périmètre de scan ou délai dépassé)"}[p["status"]]
                 if p["kind"] == "cve" else "Source : OSINT passif")
    return "\n".join(lines)


def dispatch():
    """Prévient GREEN LANTERN. Prophétie confirmée : tout de suite. Non vérifiée : après le délai de vérification."""
    if not NOTIFY:
        return 0
    rows = martian("GET", "/prophecies", params={"status": "confirmed,open", "min_priority": NOTIFY_MIN})["prophecies"]
    sent = 0
    for p in rows:
        if p.get("notified_at"):
            continue
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(p["created_at"])).total_seconds() / 3600
        if p["status"] == "open" and p["kind"] == "cve" and age_h < VERIFY_TIMEOUT_H:
            continue  # on laisse GREEN ARROW vérifier d'abord
        sev = "critical" if float(p["priority"]) >= 90 else "high" if float(p["priority"]) >= 70 else "medium"
        try:
            httpx.post(GREEN_LANTERN + "/notify", timeout=15, json={
                "title": "ORACLE — prophétie", "body": notify_text(p)[:1700], "severity": sev}).raise_for_status()
            martian("PATCH", f"/prophecies/{p['id']}", json={"status": "notified", "mark_notified": True,
                                                              "evidence": {"by": "GREEN LANTERN", "severity": sev}})
            sent += 1
        except Exception as ex:
            log("notification impossible (nouvel essai):", p["key"], ex)
            break
    return sent


def loop(fn, every, name):
    while True:
        try:
            fn()
        except Exception as ex:
            log(f"{name} en échec:", ex)
        time.sleep(every)


if __name__ == "__main__":
    if not ENABLED:
        log("désactivé (PROPHET_ENABLED=NO)")
        sys.exit(0)
    log(f"démarré — cycle {INTERVAL}s, notif ≥ {NOTIFY_MIN}, vérification {VERIFY_TIMEOUT_H}h")
    time.sleep(20)  # laisse MARTIAN et GREEN ARROW démarrer
    threading.Thread(target=loop, args=(dispatch, 60, "dispatch"), daemon=True).start()
    loop(cycle, INTERVAL, "cycle")
