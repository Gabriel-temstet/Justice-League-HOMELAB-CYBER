#!/usr/bin/env python3
"""Lance automatiquement les outils d'audit (dossier tools/) au demarrage du conteneur.
- audit local (psutil) : toujours
- decouverte ARP + scan TCP : uniquement sur AUTHORIZED_CIDRS (vide = desactive)
Resultats (CSV) dans /results. Repete toutes les AUDIT_INTERVAL secondes."""
import os, sys, time, csv, traceback
sys.path.insert(0, os.getenv("TOOLS_DIR", "/app/tools"))
RESULTS = os.getenv("RESULTS_DIR", "/results")
os.makedirs(RESULTS, exist_ok=True); os.chdir(RESULTS)
import audit_ports_localmachine as local
import audit_reseau_machine_distante as net

CIDRS = os.getenv("AUTHORIZED_CIDRS", "").split()
INTERVAL = int(os.getenv("AUDIT_INTERVAL", "86400"))
FULL = os.getenv("SCAN_FULL_PORTS", "NO").upper() == "YES"

def cycle():
    print("== audit ports locaux ==", flush=True)
    local.scan()
    for cidr in CIDRS:
        try:
            devices = net.discover_devices(cidr)
        except Exception as e:
            print(f"[{cidr}] decouverte impossible : {e}", flush=True); continue
        print(f"[{cidr}] {len(devices)} equipement(s)", flush=True)
        if not devices: continue
        with open(f"equipements_{cidr.replace('/', '_')}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=devices[0].keys(), delimiter=";"); w.writeheader(); w.writerows(devices)
        if FULL:
            for d in devices:
                net.scan_device_ports(d["IP"])
    print("== cycle termine ==", flush=True)

while True:
    try: cycle()
    except Exception: traceback.print_exc()
    sys.stdout.flush(); time.sleep(INTERVAL)
