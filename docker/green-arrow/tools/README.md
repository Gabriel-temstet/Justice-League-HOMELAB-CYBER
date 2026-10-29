# Outils d'audit réseau et ports

Deux scripts Python à but **éducatif** et d'**audit autorisé** :

| Script | Rôle |
|---|---|
| `audit_ports_localmachine.py` | Inventaire des ports TCP en écoute et des sockets UDP de **la machine locale**, avec processus, PID, exécutable et service probable. Export CSV. |
| `audit_reseau_machine_distante.py` | Découverte des équipements d'un sous-réseau privé IPv4 via **ARP** (IP, MAC, nom DNS inverse), puis scan TCP (ports 1 à 65535) de l'équipement choisi. Export CSV. |

## ⚠️ Avertissement légal

Scanner un réseau ou une machine **sans autorisation** est illégal dans de
nombreux pays (en France : articles 323-1 et suivants du Code pénal).
Utilisez ces outils **uniquement** :

- dans un but éducatif, sur vos propres machines ou votre propre laboratoire ;
- ou sur des systèmes pour lesquels vous avez une **autorisation écrite** du propriétaire.

Voir le fichier [LICENSE](LICENSE) : usage restreint, aucune utilisation
commerciale ni redistribution sans accord écrit.

## Prérequis

- Python **3.10 ou supérieur**
- Bibliothèques : `psutil` (ports locaux), `scapy` (découverte ARP)

```bash
python -m pip install -r requirements.txt
```

Vérification :

```bash
python -c "import psutil, scapy; print('Dépendances OK')"
```

### Dépendances système (script réseau uniquement)

| Système | Prérequis |
|---|---|
| Windows | [Npcap](https://npcap.com/) installé, terminal lancé en administrateur |
| Linux | root ou capacité `CAP_NET_RAW`, interface réseau active |
| macOS | privilèges suffisants (sudo), interface réseau active |

## Utilisation

### 1. Audit de la machine locale

```bash
python audit_ports_localmachine.py
```

Sans droits élevés, certains processus apparaissent comme « Inaccessible » ;
relancez en administrateur/root pour un résultat complet. Rapport :
`audit_ports.csv` (dossier courant, séparateur `;`).

### 2. Audit d'un réseau local

```bash
# Linux / macOS
sudo python3 audit_reseau_machine_distante.py

# Windows (terminal administrateur)
py audit_reseau_machine_distante.py
```

Étapes :

1. Saisir le sous-réseau IPv4 privé (ex. `192.168.1.0/24`).
2. Le script liste les équipements ayant répondu à ARP et écrit
   `equipements_reseau.csv`.
3. Choisir un numéro d'équipement pour lancer le scan TCP complet
   (rapport `ports_<ip>.csv`), ou appuyer sur Entrée pour quitter.

## Limites connues

- Seuls les sous-réseaux **privés IPv4** de **4096 adresses maximum** sont acceptés.
- ARP ne fonctionne que sur le **même segment réseau** (pas à travers un routeur).
- Le scan ne couvre que **TCP** ; les ports filtrés par un pare-feu peuvent apparaître fermés.
- Le scan complet ouvre jusqu'à 200 connexions simultanées et peut déclencher
  des alertes (IDS/pare-feu) ou perturber des équipements fragiles.
- Le « service probable » est indicatif, basé sur le numéro de port, pas sur une identification certaine.
- Les résultats dépendent des permissions du système.

## Licence

Licence personnalisée **Éducation et usage autorisé uniquement** : voir [LICENSE](LICENSE).
Il ne s'agit pas d'une licence open source.
