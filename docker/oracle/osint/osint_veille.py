#!/usr/bin/env python3
"""osint_veille.py - OSINT passif permanent sur une liste de domaines.
Stdlib uniquement. Meme code sur macOS et Linux.
Usage:
  python3 osint_veille.py                   un passage + rapport final, puis stop
  python3 osint_veille.py --loop            boucle permanente (toutes les 6 h par defaut)
  python3 osint_veille.py --add exemple.fr  ajoute un domaine
Passif: DNS (DoH), journaux Certificate Transparency, certificat TLS et en-tetes
HTTP de TA cible (une requete HEAD/GET normale). Aucun scan de ports, aucun test d'intrusion.
A utiliser sur des domaines qui t'appartiennent, ceux de clients avec accord, ou pour du prospect en sources publiques.
"""
import argparse, json, re, socket, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home() / "veille-osint"
DOMAINS = HOME / "domaines.txt"
STATE = HOME / "etat.json"
REPORTS = HOME / "rapports"
LOG = HOME / "osint.log"
UA = {"User-Agent": "osint-veille/1.0 (passif)"}
HEADERS = ["strict-transport-security", "content-security-policy", "x-frame-options",
           "x-content-type-options", "referrer-policy", "permissions-policy"]

def now(): return datetime.now(timezone.utc).astimezone()
def log(m):
    HOME.mkdir(parents=True, exist_ok=True)
    line = f"{now():%Y-%m-%d %H:%M:%S} {m}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f: f.write(line + "\n")

def get(url, timeout=25, retries=2):
    err = None
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            err = e; time.sleep(2 * (i + 1))
    raise err

def doh(name, rtype):
    """Resolution DNS via DNS-over-HTTPS (pas besoin de dig/dnspython)."""
    for base in ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve"):
        try:
            h = dict(UA, Accept="application/dns-json")
            u = f"{base}?name={urllib.parse.quote(name)}&type={rtype}"
            with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=15) as r:
                j = json.loads(r.read())
            return sorted(a["data"].strip('"').rstrip(".") if rtype != "TXT" else a["data"].replace('" "', "").strip('"')
                          for a in j.get("Answer", []) if a.get("type") in (1, 28, 15, 2, 16, 5))
        except Exception:
            continue
    return None  # echec (different de "vide")

def ct_subdomains(domain):
    """Sous-domaines vus dans les certificats publics (crt.sh, repli certspotter)."""
    subs = set()
    try:
        data = json.loads(get(f"https://crt.sh/?q=%25.{domain}&output=json", timeout=40, retries=2))
        for row in data:
            for n in row.get("name_value", "").split("\n"):
                subs.add(n.strip().lower().lstrip("*."))
    except Exception as e:
        log(f"crt.sh KO pour {domain}: {e}; repli certspotter")
        try:
            u = f"https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"
            for row in json.loads(get(u, timeout=30)):
                for n in row.get("dns_names", []): subs.add(n.strip().lower().lstrip("*."))
        except Exception as e2:
            log(f"certspotter KO pour {domain}: {e2}"); return None
    return sorted(s for s in subs if s == domain or s.endswith("." + domain))

def tls_info(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                c = ss.getpeercert()
        exp = datetime.strptime(c["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        iss = dict(x[0] for x in c["issuer"]).get("organizationName", "?")
        return {"expire": exp.date().isoformat(), "jours": (exp - datetime.now(timezone.utc)).days, "emetteur": iss}
    except Exception as e:
        return {"erreur": str(e)[:80]}

def http_info(host):
    try:
        req = urllib.request.Request(f"https://{host}/", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            h = {k.lower(): v for k, v in r.headers.items()}
        out = {k: ("present" if k in h else "absent") for k in HEADERS}
        out["server"] = h.get("server", ""); out["x-powered-by"] = h.get("x-powered-by", "")
        return out
    except Exception as e:
        return {"erreur": str(e)[:80]}

def snapshot(domain, old):
    s = {}
    for t in ("A", "AAAA", "MX", "NS", "TXT"):
        v = doh(domain, t)
        s[t] = v if v is not None else (old or {}).get(t, [])
    txt = s["TXT"]
    s["spf"] = next((x for x in txt if x.lower().startswith("v=spf1")), "")
    d = doh("_dmarc." + domain, "TXT")
    s["dmarc"] = next((x for x in (d or []) if x.lower().startswith("v=dmarc1")), "") if d is not None else (old or {}).get("dmarc", "")
    s["tls"] = tls_info(domain)
    s["http"] = http_info(domain)
    subs = ct_subdomains(domain)
    s["subs"] = subs if subs is not None else (old or {}).get("subs", [])
    return s

def dmarc_policy(d):
    m = re.search(r"\bp=(\w+)", d or ""); return m.group(1).lower() if m else "aucune"

def diff(domain, o, n):
    """Retourne liste de (severite, titre, detail, pourquoi)."""
    ev = []
    for sub in sorted(set(n["subs"]) - set(o["subs"])):
        ev.append(("MOYEN", f"Nouveau sous-domaine : {sub}",
                   f"Apparu dans les certificats publics (CT) de {domain}.",
                   "Un nouveau sous-domaine = nouvelle surface d'attaque (ou un oubli : test, staging, shadow IT). A verifier et a ajouter a l'inventaire."))
    for k, lab in (("A", "IPv4"), ("AAAA", "IPv6"), ("MX", "serveurs mail"), ("NS", "serveurs DNS")):
        if o.get(k) != n.get(k) and (o.get(k) or n.get(k)):
            sev = "ELEVE" if k == "NS" else "MOYEN"
            ev.append((sev, f"Changement {lab} sur {domain}", f"Avant : {o.get(k)}\nApres : {n.get(k)}",
                       "Un changement DNS est normal en migration, mais c'est aussi la trace d'un detournement ou d'un nouveau prestataire non declare."))
    if o["spf"] != n["spf"]:
        ev.append(("MOYEN", "SPF modifie", f"Avant : {o['spf'] or 'absent'}\nApres : {n['spf'] or 'absent'}",
                   "SPF trop large (+all, ?all) ou supprime facilite l'usurpation de ton domaine par mail."))
    if o["dmarc"] != n["dmarc"]:
        pa, pn = dmarc_policy(o["dmarc"]), dmarc_policy(n["dmarc"])
        sev = "ELEVE" if pn in ("none", "aucune") and pa not in ("none", "aucune") else "MOYEN"
        ev.append((sev, f"DMARC modifie ({pa} -> {pn})", f"Avant : {o['dmarc'] or 'absent'}\nApres : {n['dmarc'] or 'absent'}",
                   "p=none ne bloque rien. Quarantine/reject est ce qui protege reellement contre le phishing en ton nom (et pese dans les exigences NIS2 de bonne hygiene mail)."))
    ot, nt = o.get("tls", {}), n.get("tls", {})
    if "expire" in nt:
        if nt["jours"] <= 14 and (ot.get("jours", 99) > 14 or "expire" not in ot):
            ev.append(("CRITIQUE" if nt["jours"] <= 3 else "ELEVE", f"Certificat TLS expire dans {nt['jours']} jours",
                       f"Expire le {nt['expire']} (emetteur : {nt['emetteur']}).", "Certificat expire = alertes navigateur, perte de confiance, service coupe."))
        if ot.get("expire") and ot["expire"] != nt["expire"]:
            ev.append(("INFO", "Certificat TLS renouvele/change", f"Avant : {ot.get('expire')} ({ot.get('emetteur')})\nApres : {nt['expire']} ({nt['emetteur']})",
                       "Renouvellement normal, sauf si l'emetteur change sans que tu l'aies demande."))
    elif "erreur" in nt and "expire" in ot:
        ev.append(("ELEVE", "TLS ne repond plus correctement", nt["erreur"], "Certificat invalide/expire ou service HTTPS tombe."))
    oh, nh = o.get("http", {}), n.get("http", {})
    for k in HEADERS:
        if oh.get(k) == "present" and nh.get(k) == "absent":
            ev.append(("MOYEN", f"En-tete de securite retire : {k}", "", "Regression de durcissement web (souvent un changement de config ou de CDN)."))
    for k in ("server", "x-powered-by"):
        if oh.get(k) != nh.get(k) and (oh.get(k) or nh.get(k)):
            ev.append(("INFO", f"Technologie annoncee modifiee ({k})", f"Avant : {oh.get(k) or '-'}\nApres : {nh.get(k) or '-'}",
                       "Reveler la techno/version aide un attaquant a cibler des failles connues."))
    return ev

def first_baseline(domain, n):
    miss = [h for h in HEADERS if n.get("http", {}).get(h) == "absent"]
    lines = [f"- Sous-domaines vus en CT : {len(n['subs'])}", f"- IP : {', '.join(n['A'] + n['AAAA']) or '-'}",
             f"- MX : {', '.join(n['MX']) or '-'}", f"- SPF : {n['spf'] or 'ABSENT'}",
             f"- DMARC : {n['dmarc'] or 'ABSENT'} (politique : {dmarc_policy(n['dmarc'])})",
             f"- TLS : {n['tls']}", f"- En-tetes de securite absents : {', '.join(miss) or 'aucun'}"]
    return "\n".join(lines)

def write_report(domain, sev, title, detail, why):
    REPORTS.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:50].strip("-")
    p = REPORTS / f"{now():%Y%m%d-%H%M%S}-{domain}-{slug}.md"
    p.write_text(f"# [{sev}] {title}\n\n- Domaine : {domain}\n- Detecte : {now():%Y-%m-%d %H:%M}\n- Source : DNS public, Certificate Transparency, TLS/HTTP public\n\n"
                 f"## Ce qui a change\n{detail or '(voir titre)'}\n\n## Pourquoi c'est important\n{why}\n\n"
                 f"## Pour ton activite\nAudit reseau / MSP / NIS2 : a ajouter a l'inventaire du client ou a ton prospect. Cours B3 : bon exemple de surface d'attaque qui evolue.\n", encoding="utf-8")
    return p

def daily(state, events_today):
    p = REPORTS / f"synthese-{now():%Y-%m-%d}.md"
    L = [f"# Synthese OSINT du {now():%Y-%m-%d}\n", f"Domaines surveilles : {len(state)}\n"]
    for d, s in sorted(state.items()):
        t = s.get("tls", {})
        L.append(f"- {d} : {len(s['subs'])} sous-domaines, DMARC {dmarc_policy(s['dmarc'])}, TLS {t.get('jours', '?')} j restants")
    L.append("\n## Evenements du jour")
    L += [f"- [{e[0]}] {e[1]}" for e in events_today] or ["- rien de nouveau"]
    REPORTS.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(L) + "\n", encoding="utf-8")

def final_report(state, events):
    """Rapport final consolide : tout ce qui a ete trouve, par domaine, + changements depuis le passage precedent."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    p = REPORTS / f"RAPPORT-FINAL-{now():%Y%m%d-%H%M}.md"
    L = [f"# Rapport OSINT final - {now():%Y-%m-%d %H:%M}\n", f"Domaines analyses : {len(state)} (sources publiques, passif)\n", "## Changements depuis le passage precedent"]
    L += [f"- [{e[0]}] {e[1]}" for e in events if not e[1].startswith("Etat initial")] or ["- aucun (ou premier passage)"]
    L.append("\n## Resume par domaine\n\n| Domaine | Sous-dom. | DMARC | SPF | TLS (jours) | En-tetes absents |\n|---|---|---|---|---|---|")
    for d, n in sorted(state.items()):
        miss = [h for h in HEADERS if n.get("http", {}).get(h) == "absent"]
        L.append(f"| {d} | {len(n['subs'])} | {dmarc_policy(n['dmarc'])} | {'oui' if n['spf'] else 'NON'} | {n['tls'].get('jours', '?')} | {len(miss)}/{len(HEADERS)} |")
    for d, n in sorted(state.items()):
        L.append(f"\n## {d}\n" + first_baseline(d, n))
        L.append("- Liste des sous-domaines : " + (", ".join(n["subs"][:200]) or "-"))
        pts = []
        if not n["spf"]: pts.append("SPF absent : usurpation mail possible")
        if dmarc_policy(n["dmarc"]) in ("none", "aucune"): pts.append("DMARC absent ou p=none : aucun blocage du phishing en son nom")
        if n["tls"].get("jours", 99) <= 30: pts.append("certificat TLS a renouveler sous 30 jours")
        if n.get("http", {}).get("strict-transport-security") == "absent": pts.append("HSTS absent")
        L.append("- Points d'attention : " + ("; ".join(pts) or "aucun point majeur releve"))
    L.append("\n_Limites : passif uniquement ; pas de scan de ports ; pas de recherche de fuites ; les logs CT ne listent que les sous-domaines ayant un certificat public._")
    p.write_text("\n".join(L) + "\n", encoding="utf-8"); return p

def load_domains():
    if not DOMAINS.exists(): return []
    return [l.strip().lower() for l in DOMAINS.read_text().splitlines() if l.strip() and not l.startswith("#")]

def run_once():
    HOME.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    doms = load_domains()
    if not doms: log(f"Aucun domaine. Ajoute-en : python3 osint_veille.py --add exemple.fr  (ou edite {DOMAINS})"); return
    today = []
    for d in doms:
        try:
            n = snapshot(d, state.get(d))
        except Exception as e:
            log(f"{d}: erreur {e}"); continue
        if d not in state:
            p = write_report(d, "INFO", f"Etat initial de {d}", first_baseline(d, n), "Point de depart : les prochains rapports ne montreront que les changements.")
            log(f"{d}: etat initial -> {p.name}"); today.append(("INFO", f"Etat initial de {d}"))
        else:
            for sev, t, det, why in diff(d, state[d], n):
                p = write_report(d, sev, t, det, why); today.append((sev, f"{d} : {t}")); log(f"{d}: {sev} {t}")
        state[d] = n
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    daily(state, today)
    log(f"Rapport final : {final_report(state, today).name}")
    log(f"Passage termine ({len(doms)} domaines, {len(today)} rapports)")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--loop", action="store_true", help="tourne en permanence")
    ap.add_argument("--hours", type=float, default=6); ap.add_argument("--add")
    a = ap.parse_args(); HOME.mkdir(parents=True, exist_ok=True)
    if a.add:
        cur = load_domains(); d = a.add.lower().strip()
        if d not in cur: DOMAINS.write_text("\n".join(cur + [d]) + "\n")
        print("OK:", d); return
    while True:
        try: run_once()
        except Exception as e: log(f"erreur globale: {e}")
        if not a.loop: break
        time.sleep(a.hours * 3600)

if __name__ == "__main__": main()
