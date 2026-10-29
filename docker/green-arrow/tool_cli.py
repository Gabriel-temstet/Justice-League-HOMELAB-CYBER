#!/usr/bin/env python3
"""CLI non interactive appelee par la console web (docker exec) : local | discover CIDR | portscan IP | nmap IP.
Toute cible reseau est verifiee contre AUTHORIZED_CIDRS (variable d'environnement du conteneur)."""
import os, sys, csv, ipaddress, subprocess
sys.path.insert(0, os.getenv("TOOLS_DIR", "/app/tools"))
RESULTS = os.getenv("RESULTS_DIR", "/results")
os.makedirs(RESULTS, exist_ok=True); os.chdir(RESULTS)
AUTH = []
for c in os.getenv("AUTHORIZED_CIDRS", "").split():
    try: AUTH.append(ipaddress.ip_network(c, strict=False))
    except ValueError: pass

def die(msg, code=2): print("ERREUR:", msg, flush=True); sys.exit(code)
def check_cidr(text):
    try: n = ipaddress.ip_network(text, strict=False)
    except ValueError: die("CIDR invalide")
    if not any(n.version == a.version and n.subnet_of(a) for a in AUTH): die(f"{n} hors de AUTHORIZED_CIDRS")
    return n
def check_ip(text):
    try: ip = ipaddress.ip_address(text)
    except ValueError: die("adresse IP invalide")
    if not any(ip in a for a in AUTH): die(f"{ip} hors de AUTHORIZED_CIDRS")
    return str(ip)

def main():
    if len(sys.argv) < 2: die("usage: tool_cli.py local|discover CIDR|portscan IP|nmap IP")
    cmd = sys.argv[1]
    if cmd == "local":
        import audit_ports_localmachine as m; m.scan()
    elif cmd == "discover" and len(sys.argv) == 3:
        import audit_reseau_machine_distante as net
        n = check_cidr(sys.argv[2])
        devs = net.discover_devices(str(n))
        print(f"{len(devs)} equipement(s) sur {n}")
        for d in devs: print(f"  {d['IP']:<16} {d['MAC']}  {d['Nom']}")
        if devs:
            fn = f"equipements_{str(n).replace('/', '_')}.csv"
            with open(fn, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=devs[0].keys(), delimiter=";"); w.writeheader(); w.writerows(devs)
            print("Rapport:", fn)
    elif cmd == "portscan" and len(sys.argv) == 3:
        import audit_reseau_machine_distante as net
        net.scan_device_ports(check_ip(sys.argv[2]))
    elif cmd == "nmap" and len(sys.argv) == 3:
        ip = check_ip(sys.argv[2])
        sys.exit(subprocess.call(["nmap", "-sV", "--top-ports", "100", "-T4", "-oN", f"nmap_{ip.replace('.', '_')}.txt", ip]))
    else: die("commande inconnue")

main()
