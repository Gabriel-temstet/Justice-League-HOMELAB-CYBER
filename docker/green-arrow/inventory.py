#!/usr/bin/env python3
"""GREEN ARROW — inventaire services/versions + vérification des prophéties d'ORACLE.

1. Découverte (nmap -sn) puis relevé des services (nmap -sV, ports courants) sur AUTHORIZED_CIDRS
   uniquement ; résultat publié dans MARTIAN (entité `asset_services`) — c'est ce qui permet à
   ORACLE de croiser les CVE avec ce qui tourne réellement chez vous.
2. Vérification : pour chaque prophétie `open`, GREEN ARROW re-sonde UNIQUEMENT l'actif et le port
   concernés (dans le périmètre autorisé) et rapporte confirmed / refuted à MARTIAN.

Garde-fous : périmètre strict (AUTHORIZED_CIDRS vide = tout désactivé), aucune exécution via shell,
IPv4 validées, nombre de re-sondes par minute plafonné, aucune action offensive (détection de version
uniquement, `--version-light`). Stdlib uniquement.
"""
import ipaddress
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

MARTIAN = os.getenv("MARTIAN_URL", "http://martian-core:8787")
TOKEN = os.getenv("AI_GATEWAY_TOKEN", "")
CIDRS = [c for c in os.getenv("AUTHORIZED_CIDRS", "").split() if c]
INTERVAL = int(os.getenv("DISCOVERY_INTERVAL", "3600"))
TOP_PORTS = max(1, min(int(os.getenv("SERVICE_TOP_PORTS", "100")), 1000))
VERIFY = os.getenv("PROPHECY_VERIFY", "YES").upper() == "YES"
VERIFY_POLL = int(os.getenv("PROPHECY_VERIFY_POLL", "60"))
VERIFY_COOLDOWN = int(os.getenv("PROPHECY_VERIFY_COOLDOWN", "3600"))
VERIFY_BATCH = int(os.getenv("PROPHECY_VERIFY_BATCH", "5"))
NMAP_TIMEOUT = int(os.getenv("NMAP_TIMEOUT", "900"))

try:
    NETS = [ipaddress.ip_network(c, strict=False) for c in CIDRS]
except ValueError as ex:
    print("AUTHORIZED_CIDRS invalide:", ex, flush=True)
    NETS = []


def log(*a):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "[inventory]", *a, flush=True)


# ----------------------------------------------------------------------------- garde-fous
def in_scope(ip):
    """Vrai uniquement pour une IPv4 littérale incluse dans AUTHORIZED_CIDRS."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and any(a in n for n in NETS)


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


# ----------------------------------------------------------------------------- nmap
def run_nmap(args):
    """nmap sans shell ; retourne stdout ou None."""
    try:
        r = subprocess.run(["nmap", *args], capture_output=True, text=True, timeout=NMAP_TIMEOUT)
        return r.stdout if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError) as ex:
        log("nmap:", ex)
        return None


def discover(cidr):
    out = run_nmap(["-sn", "-n", cidr, "-oG", "-"])
    ips = []
    for line in (out or "").splitlines():
        if line.startswith("Host:") and line.rstrip().endswith("Status: Up"):
            ip = line.split()[1]
            if in_scope(ip):
                ips.append(ip)
    return ips


def parse_services(xml_text):
    """Sortie nmap -oX -> liste de ports {port, proto, state, name, product, version, cpe[]}."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for p in root.iter("port"):
        st = p.find("state")
        sv = p.find("service")
        out.append({
            "port": int(p.get("portid")), "proto": p.get("protocol", "tcp"),
            "state": st.get("state") if st is not None else "unknown",
            "name": sv.get("name", "") if sv is not None else "",
            "product": sv.get("product", "") if sv is not None else "",
            "version": sv.get("version", "") if sv is not None else "",
            "cpe": [c.text for c in sv.findall("cpe") if c.text] if sv is not None else [],
        })
    return out


def scan_services(ip, port=None):
    if not in_scope(ip):
        raise ValueError(f"{ip} hors AUTHORIZED_CIDRS")
    ports = ["-p", str(int(port))] if port else ["--top-ports", str(TOP_PORTS)]
    out = run_nmap(["-sV", "--version-light", "-Pn", "-n", "-T3", *ports, "-oX", "-", ip])
    return None if out is None else parse_services(out)


# ----------------------------------------------------------------------------- MARTIAN
def call(method, path, body=None):
    req = urllib.request.Request(
        MARTIAN + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "X-AI-Gateway-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def publish_inventory(ip, services):
    opened = [s for s in services if s["state"] == "open"]
    call("POST", "/memory/entity", {"entity_type": "asset_services", "external_id": ip, "data": {
        "ip": ip, "scanned_at": datetime.now(timezone.utc).isoformat(), "source": "GREEN-ARROW", "services": opened}})


def publish_asset(ip):
    call("POST", "/memory/entity", {"entity_type": "asset", "external_id": ip,
                                    "data": {"ip": ip, "source": "GREEN-ARROW"}})


# ----------------------------------------------------------------------------- boucle d'inventaire
def inventory_cycle():
    for cidr in CIDRS:
        ips = discover(cidr)
        log(f"[{cidr}] {len(ips)} hôte(s) actif(s)")
        for ip in ips:
            try:
                publish_asset(ip)
                svc = scan_services(ip)
                if svc is not None:
                    publish_inventory(ip, svc)
                    log(f"{ip}: {sum(1 for s in svc if s['state'] == 'open')} service(s) ouvert(s)")
            except Exception as ex:
                log("échec", ip, ex)


# ----------------------------------------------------------------------------- vérification des prophéties
_verified = {}  # prophecy id -> timestamp


def verify_prophecy(p):
    """Re-sonde l'actif/port visé. Retourne 'confirmed' | 'refuted' | None (non concluant)."""
    ip, port = p.get("asset"), p.get("port")
    expected = (p.get("rationale") or {}).get("cpe")
    if not (ip and port and expected and 0 < int(port) < 65536 and in_scope(ip)):
        return None
    svc = scan_services(ip, port)
    if svc is None:
        return None
    hit = next((s for s in svc if s["port"] == int(port)), None)
    if hit is None:
        return None
    now = datetime.now(timezone.utc).isoformat()
    if hit["state"] == "open":
        seen = {cpe_to_23(c) for c in hit["cpe"]}
        if expected in seen:
            call("PATCH", f"/prophecies/{p['id']}", {"status": "confirmed", "evidence": {
                "by": "GREEN ARROW", "check": "rescan -sV", "port_open": True, "cpe": expected, "scanned_at": now}})
            return "confirmed"
        if seen - {None}:  # service ouvert mais autre version : corrigé ou remplacé
            full = scan_services(ip)
            if full is not None:
                publish_inventory(ip, full)
            call("PATCH", f"/prophecies/{p['id']}", {"status": "refuted", "evidence": {
                "by": "GREEN ARROW", "check": "rescan -sV", "port_open": True, "cpe_found": sorted(seen - {None}),
                "cpe_expected": expected, "scanned_at": now}})
            return "refuted"
        return None  # ouvert mais version non identifiée : non concluant
    if hit["state"] == "closed":  # RST explicite ; « filtered » reste non concluant (hôte éteint, pare-feu)
        full = scan_services(ip)
        if full is not None:
            publish_inventory(ip, full)
        call("PATCH", f"/prophecies/{p['id']}", {"status": "refuted", "evidence": {
            "by": "GREEN ARROW", "check": "rescan -sV", "port_open": False, "scanned_at": now}})
        return "refuted"
    return None


def verify_cycle():
    rows = call("GET", "/prophecies?status=open&kind=cve&limit=200")["prophecies"]
    done = 0
    for p in rows:
        if done >= VERIFY_BATCH:
            break
        if time.time() - _verified.get(p["id"], 0) < VERIFY_COOLDOWN:
            continue
        _verified[p["id"]] = time.time()
        try:
            res = verify_prophecy(p)
            log(f"vérification {p['key']}: {res or 'non concluant / hors périmètre'}")
            if res:
                done += 1
        except Exception as ex:
            log("vérification en échec", p.get("key"), ex)


def loop(fn, every, name):
    while True:
        try:
            fn()
        except Exception as ex:
            log(f"{name} en échec:", ex)
        time.sleep(every)


if __name__ == "__main__":
    if not NETS:
        log("AUTHORIZED_CIDRS vide : inventaire et vérification désactivés")
        while True:
            time.sleep(3600)
    log(f"périmètre: {', '.join(CIDRS)} — top {TOP_PORTS} ports, vérification {'ON' if VERIFY else 'OFF'}")
    if VERIFY:
        threading.Thread(target=loop, args=(verify_cycle, VERIFY_POLL, "vérification"), daemon=True).start()
    loop(inventory_cycle, INTERVAL, "inventaire")
