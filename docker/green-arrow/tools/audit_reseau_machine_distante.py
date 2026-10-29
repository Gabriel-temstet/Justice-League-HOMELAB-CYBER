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
import ipaddress
import socket
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed

from scapy.all import ARP, Ether, srp


def discover_devices(network_text):
    network = ipaddress.ip_network(network_text, strict=False)

    if not network.is_private:
        raise ValueError("Utilise un sous-réseau privé de ton réseau local.")

    if network.version != 4:
        raise ValueError("Cette version utilise ARP sur IPv4.")

    if network.num_addresses > 4096:
        raise ValueError(
            "Sous-réseau trop grand. Limite cette analyse à 4096 adresses."
        )

    print(f"\nDécouverte ARP sur {network}...")

    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=str(network))

    answered, _ = srp(packet, timeout=3, retry=1, verbose=False)

    devices = []

    for _, response in answered:
        ip = response.psrc
        mac = response.hwsrc

        try:
            hostname, aliases, _ = socket.gethostbyaddr(ip)
            fqdn = hostname if "." in hostname else "FQDN non confirmé"
            if hostname == ip:
                fqdn = "FQDN non confirmé"
        except (socket.herror, socket.gaierror, OSError):
            hostname = "Inconnu"
            fqdn = "Non résolu par DNS inverse"

        devices.append({
            "IP": ip,
            "MAC": mac,
            "Nom": hostname,
            "FQDN": fqdn,
        })

    devices.sort(key=lambda item: ipaddress.ip_address(item["IP"]))
    return devices


def scan_tcp_port(ip, port, timeout=0.35):
    """Une connexion TCP réussie indique un port accessible."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        if sock.connect_ex((ip, port)) == 0:
            try:
                service = socket.getservbyport(port, "tcp")
            except OSError:
                service = "Inconnu"

            return {
                "IP": ip,
                "Port": port,
                "Protocole": "TCP",
                "État": "Ouvert",
                "Service probable": service,
            }
    except OSError:
        pass
    finally:
        sock.close()

    return None


def scan_device_ports(ip):
    print(f"\nAnalyse TCP de {ip}, ports 1 à 65535...")
    print("Cela peut prendre plusieurs minutes.")

    results = []

    # Nombre de connexions simultanées limité pour réduire la charge.
    with ThreadPoolExecutor(max_workers=200) as executor:
        futures = [
            executor.submit(scan_tcp_port, ip, port)
            for port in range(1, 65536)
        ]

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                print(
                    f"Port {result['Port']}/TCP ouvert"
                    f" - {result['Service probable']}"
                )

    results.sort(key=lambda item: item["Port"])

    filename = f"ports_{ip.replace('.', '_')}.csv"
    if results:
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=results[0].keys(), delimiter=";"
            )
            writer.writeheader()
            writer.writerows(results)

    print(f"\nPorts TCP ouverts détectés : {len(results)}")
    print(f"Rapport : {filename}")
    return results


def main():
    print(f"Audit réseau local - {platform.system()}")
    print("À utiliser uniquement sur un réseau que tu es autorisé à auditer.")

    network_text = input(
        "\nSous-réseau IPv4 (ex. 192.168.1.0/24) : "
    ).strip()

    try:
        devices = discover_devices(network_text)
    except (ValueError, OSError, PermissionError) as exc:
        print(f"Erreur : {exc}")
        return

    if not devices:
        print(
            "\nAucun équipement n'a répondu à ARP. "
            "Vérifie le sous-réseau, les permissions et l'interface réseau."
        )
        return

    print("\nÉQUIPEMENTS DÉTECTÉS")
    print("-" * 90)

    for index, device in enumerate(devices, start=1):
        print(
            f"{index}. IP : {device['IP']}\n"
            f"   MAC  : {device['MAC']}\n"
            f"   Nom  : {device['Nom']}\n"
            f"   FQDN : {device['FQDN']}\n"
        )

    with open("equipements_reseau.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=devices[0].keys(), delimiter=";"
        )
        writer.writeheader()
        writer.writerows(devices)

    choice = input(
        "Numéro de l'équipement à analyser (Entrée pour quitter) : "
    ).strip()

    if not choice:
        return

    try:
        index = int(choice) - 1
        if index < 0 or index >= len(devices):
            raise ValueError
    except ValueError:
        print("Sélection invalide.")
        return

    scan_device_ports(devices[index]["IP"])


if __name__ == "__main__":
    main()
