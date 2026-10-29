#!/usr/bin/env python3
# =============================================================================
# DEPENDANCES ET BIBLIOTHEQUES A INSTALLER
# =============================================================================
#
# Python requis :
#   Python 3.10 ou supérieur
#
# 1. SCRIPT audit_ports.py
#    Bibliothèques Python :
#      - psutil : inventaire des sockets, ports et processus locaux
#
#    Installation :
#      python -m pip install psutil
#
# 2. SCRIPT audit_reseau.py
#    Bibliothèques Python :
#      - scapy : découverte des équipements via ARP
#
#    Installation :
#      python -m pip install scapy
#
# 3. DEPENDANCES SYSTEME POUR audit_reseau.py
#
#    Windows :
#      - Npcap : capture et émission de paquets réseau si nécessaire
#        Téléchargement : https://npcap.com/
#      - Exécuter le terminal avec les droits nécessaires.
#
#    Linux :
#      - Privilèges root ou CAP_NET_RAW selon la configuration
#      - Interface réseau active
#
#    macOS :
#      - Privilèges suffisants pour les opérations réseau
#      - Interface réseau active
#
# 4. INSTALLATION COMPLETE DES DEPENDANCES PYTHON
#
#    Pour installer les bibliothèques des deux scripts :
#      python -m pip install psutil scapy
#
#    Sous Linux/macOS, selon l'installation de Python :
#      python3 -m pip install psutil scapy
#
#    Sous Windows :
#      py -m pip install psutil scapy
#
# 5. BIBLIOTHEQUES STANDARD UTILISEES
#
#    Ces modules sont inclus dans Python et ne nécessitent aucune installation :
#      - socket
#      - csv
#      - platform
#      - datetime
#      - pathlib
#      - ipaddress
#      - concurrent.futures
#
# 6. VALIDATION
#
#    Vérifier l'installation :
#      python -c "import psutil, scapy; print('Dépendances OK')"
#
#    Note : l'installation de Npcap et les privilèges requis dépendent du
#    système et des opérations réseau utilisées.
#
# =============================================================================

import csv
import platform
import socket
from datetime import datetime
from pathlib import Path

import psutil


SERVICES = {
    21: "FTP",
    22: "SSH",
    25: "SMTP",
    53: "DNS",
    67: "DHCP serveur",
    68: "DHCP client",
    80: "HTTP",
    110: "POP3",
    123: "NTP",
    135: "RPC Windows",
    139: "NetBIOS",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB / partage Windows",
    465: "SMTP sécurisé",
    587: "SMTP submission",
    631: "Impression IPP",
    993: "IMAPS",
    995: "POP3S",
    1433: "Microsoft SQL Server",
    2049: "NFS",
    3306: "MySQL / MariaDB",
    3389: "Bureau à distance Windows",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8000: "HTTP / développement",
    8080: "HTTP alternatif / proxy",
    8443: "HTTPS alternatif",
    27017: "MongoDB",
}


def process_info(pid):
    """Retourne le nom et le chemin d'un processus."""
    if pid is None:
        return "Inconnu", "Inaccessible"

    try:
        proc = psutil.Process(pid)
        name = proc.name()

        try:
            path = proc.exe() or "Indisponible"
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            path = "Accès refusé ou indisponible"

        return name, path

    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return "Inaccessible", "Inaccessible"


def describe_port(port, protocol):
    """Description indicative, pas une identification certaine."""
    if port in SERVICES:
        return SERVICES[port]

    try:
        return socket.getservbyport(port, protocol.lower())
    except (OSError, OverflowError):
        return "Service non identifié"


def classify_address(ip):
    if ip in ("127.0.0.1", "::1"):
        return "Boucle locale uniquement"
    if ip in ("0.0.0.0", "::"):
        return "Toutes les interfaces"
    return "Adresse spécifique"


def scan():
    system = platform.system()
    print(f"Audit des ports - {system}")
    print(f"Date : {datetime.now().isoformat(timespec='seconds')}")

    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError) as exc:
        print(f"Accès refusé : {exc}")
        print("Relance avec les droits administrateur/root.")
        return
    except psutil.Error as exc:
        print(f"Impossible d'obtenir les sockets : {exc}")
        return

    rows = []

    for conn in connections:
        if not conn.laddr:
            continue

        if conn.type == socket.SOCK_STREAM:
            if conn.status != psutil.CONN_LISTEN:
                continue
            protocol = "TCP"

        elif conn.type == socket.SOCK_DGRAM:
            protocol = "UDP"

        else:
            continue

        ip = conn.laddr.ip
        port = conn.laddr.port
        name, executable = process_info(conn.pid)

        rows.append({
            "Protocole": protocol,
            "Adresse": ip,
            "Port": port,
            "État": (
                conn.status
                if protocol == "TCP"
                else "Socket UDP locale"
            ),
            "Processus": name,
            "PID": conn.pid if conn.pid is not None else "",
            "Exécutable": executable,
            "Service probable": describe_port(port, protocol),
            "Écoute": classify_address(ip),
        })

    rows.sort(key=lambda row: (row["Port"], row["Protocole"]))

    if not rows:
        print("Aucun port correspondant détecté.")
    else:
        for row in rows:
            print(
                f"{row['Protocole']:3} "
                f"{row['Adresse']}:{row['Port']} | "
                f"{row['Processus']} (PID {row['PID']}) | "
                f"{row['Service probable']}"
            )
            print(f"    Exécutable : {row['Exécutable']}")
            print(f"    Écoute : {row['Écoute']}")

    output = Path.cwd() / "audit_ports.csv"

    if rows:
        with output.open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=rows[0].keys(),
                delimiter=";"
            )
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nRapport CSV : {output.resolve()}")

    print(f"Entrées détectées : {len(rows)}")
    print("Les résultats dépendent des permissions du système.")


if __name__ == "__main__":
    scan()
