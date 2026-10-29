# 5. Outils intégrés

Quatre outils s'exécutent dans les conteneurs. Les trois premiers démarrent **automatiquement** avec leur conteneur et sont pilotables depuis la [Console](04-console.md).

| Outil | Conteneur | Origine | Démarrage automatique |
|---|---|---|---|
| Scanner de ports | `green-arrow` | `Scanner_de_port_ouverts.zip` | `start.sh` → `scanner.sh` + `run_audits.py` |
| OSINT passif | `oracle-cti` | `Tools_custom_OSINT.zip` | `start.sh` → `osint_veille.py --loop` + collecteur CTI |
| Veille cyber (RSS) | `justice-league-watchtower` | `Veille_techno_TOOLS_custom.zip` | `start.sh` → `veille_cyber.py` + API WATCHTOWER |
| Bug Bounty Lab | `justice-league-bug-bounty` | natif | manuel (`docker exec`) |

Chaque conteneur exécute l'outil **en parallèle** de son service d'origine ; si l'un des deux s'arrête, le conteneur s'arrête et Docker le redémarre (`restart: unless-stopped`) — sauf pour OSINT et veille, relancés en boucle par le script de démarrage.

---

## 5.1 Scanner de ports (GREEN ARROW)

> ⚠️ **Cadre légal** : scanner un réseau ou une machine sans autorisation est illégal dans de nombreux pays (France : art. 323-1 et suivants du Code pénal). Usage limité à vos machines, votre laboratoire, ou avec autorisation écrite du propriétaire. Licence de l'outil : « éducation et usage autorisé uniquement » (`docker/green-arrow/tools/LICENSE`).

### Composants

| Fichier | Rôle |
|---|---|
| `scanner.sh` | Boucle de découverte `nmap -sn` sur `AUTHORIZED_CIDRS`, enregistre chaque hôte dans MARTIAN |
| `tools/audit_ports_localmachine.py` | Inventaire des ports TCP en écoute et sockets UDP (psutil) : processus, PID, exécutable, service probable ; CSV |
| `tools/audit_reseau_machine_distante.py` | Découverte ARP (scapy) d'un sous-réseau privé IPv4 (≤ 4096 adresses) puis scan TCP 1–65535 (200 threads) |
| `run_audits.py` | Lance automatiquement les audits en boucle (`AUDIT_INTERVAL`) |
| `tool_cli.py` | Interface non interactive utilisée par la Console |
| `start.sh` | Lance `scanner.sh` et `run_audits.py` |

### Comportement automatique

À chaque cycle (`AUDIT_INTERVAL`, 24 h par défaut) : audit des ports locaux du conteneur, puis pour chaque CIDR de `AUTHORIZED_CIDRS` : découverte ARP et écriture de `equipements_<cidr>.csv` ; si `SCAN_FULL_PORTS=YES`, scan TCP complet de chaque hôte (`ports_<ip>.csv`). Résultats dans le volume `green_arrow_results` (`/results`).

### Actions de la Console

| Action | Commande exécutée dans le conteneur | Durée max |
|---|---|---|
| Audit des ports locaux | `tool_cli.py local` | 2 min |
| Découverte réseau (ARP) | `tool_cli.py discover <CIDR>` | 5 min |
| nmap rapide (top 100 + versions) | `tool_cli.py nmap <IP>` → `nmap -sV --top-ports 100 -T4` | 15 min |
| Scan TCP complet | `tool_cli.py portscan <IP>` | 60 min |

Toute IP/CIDR hors de `AUTHORIZED_CIDRS` est refusée (`ERREUR: … hors de AUTHORIZED_CIDRS`).

### Fichiers produits

| Fichier | Contenu (séparateur `;`, encodage UTF-8 BOM) |
|---|---|
| `audit_ports.csv` | Protocole, adresse, port, état, processus, PID, exécutable, service probable, portée d'écoute |
| `equipements_<cidr>.csv` | IP, MAC, nom, FQDN |
| `ports_<ip>.csv` | IP, port, protocole, état, service probable |
| `nmap_<ip>.txt` | Sortie nmap normale |

### Limites connues

- ARP ne fonctionne que sur le **même segment réseau** (pas à travers un routeur).
- Dans Docker (réseau bridge), notamment sous **macOS/Docker Desktop**, le conteneur est dans une VM/bridge : il ne voit **pas** le LAN de l'hôte, et l'audit « ports locaux » décrit le conteneur. Pour auditer l'hôte/LAN, utilisez les scripts natifs (ci-dessous) ou donnez au conteneur `network_mode: host` (Linux ; il perd alors la résolution des noms de services Docker, donc l'envoi à MARTIAN).
- Le scan TCP ne couvre pas UDP ; un pare-feu peut faire apparaître des ports filtrés comme fermés ; le « service probable » est déduit du numéro de port.
- Le scan complet peut déclencher des alertes IDS/pare-feu ou perturber des équipements fragiles.

### Utilisation native (hors Docker)

```bash
cd docker/green-arrow/tools
python3 -m pip install -r requirements.txt           # psutil, scapy
python3 audit_ports_localmachine.py                  # audit_ports.csv dans le dossier courant
sudo python3 audit_reseau_machine_distante.py        # interactif : sous-réseau puis machine à scanner
```

Prérequis : Python ≥ 3.10 ; Linux : root ou `CAP_NET_RAW` ; macOS : `sudo` ; Windows : [Npcap](https://npcap.com/) + terminal administrateur. Détails : `docker/green-arrow/tools/README.md`.

---

## 5.2 OSINT passif (ORACLE)

Surveillance permanente d'une liste de domaines, **sans scan de ports ni test d'intrusion**.

Sources passives : DNS via DNS-over-HTTPS (Cloudflare, Google), journaux **Certificate Transparency** (crt.sh, repli certspotter) pour les sous-domaines, certificat TLS (expiration…) et en-têtes HTTP de sécurité (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) — une requête normale sur la cible. Dépendances : bibliothèque standard Python uniquement.

> À utiliser sur **vos domaines**, ceux de clients avec accord, ou en sources publiques.

### Fonctionnement

- Le conteneur définit `HOME=/data/home`, donc l'outil écrit dans `/data/home/veille-osint/` (volume `oracle_data`).
- `start.sh` ajoute les domaines de `OSINT_DOMAINS` à `domaines.txt`, puis lance `osint_veille.py --loop --hours $OSINT_INTERVAL_HOURS` (6 h par défaut). La liste est relue à chaque passage : ajouter un domaine ne nécessite pas de redémarrage.
- Les nouveautés/changements génèrent des rapports classés par sévérité.

### Actions de la Console

| Action | Effet |
|---|---|
| Lancer un passage maintenant | Un cycle complet (`osint_veille.py` sans `--loop`) |
| Ajouter un domaine | `osint_veille.py --add <domaine>` (validé : nom de domaine DNS) |
| Retirer un domaine | `tool_cli.py remove <domaine>` |

Un passage manuel peut se chevaucher avec le passage automatique : ils partagent `etat.json`. Évitez de les lancer simultanément.

### Fichiers (`/data/home/veille-osint/`)

| Fichier | Contenu |
|---|---|
| `domaines.txt` | Liste de surveillance (une entrée par ligne, `#` = commentaire) |
| `etat.json` | Dernier état connu par domaine (pour détecter les changements) |
| `osint.log` | Journal |
| `rapports/` | `<horodatage>-<domaine>-<titre>.md`, `synthese-AAAA-MM-JJ.md`, `RAPPORT-FINAL-AAAAMMJJ-HHMM.md` |

Le guide d'origine (`guide-osint-veille-*.docx`) et un exemple de rapport sont dans `docker/oracle/osint/`. Les fichiers `.service` / `.plist` servent à installer l'outil comme service hôte (systemd / launchd) hors Docker.

---

## 5.3 Veille cyber

Deux mécanismes complémentaires dans WATCHTOWER :

### a) WATCHTOWER (application native, API sur `:8830`)
Flux RSS pondérés + **CISA KEV** + **NVD** (CVSS ≥ `NVD_MIN_CVSS`), score 0–100, *watchlist* de vos produits, rapports quotidien et hebdomadaire (Markdown + HTML), alertes via GREEN LANTERN. Interface HTML sur http://127.0.0.1:8830 et API ([référence](06-reference-api.md#watchtower)). Rapports dans `/data/reports`.

### b) `veille_cyber.py` (outil intégré)
Collecte 8 flux (CERT-FR, CISA, BleepingComputer, The Hacker News, SecurityWeek, Krebs on Security, ZATAZ, IT-Connect), dédoublonne (`etat.json`), génère **un rapport Markdown par nouvelle** (résumé, impact, tags métier : NIS2/conformité, PQC/crypto, MSP…) et une synthèse quotidienne. Stdlib Python uniquement ; option `--ollama MODELE` pour des résumés IA (non utilisable tel quel depuis le conteneur : l'outil vise `localhost:11434`).

- Démarrage : `start.sh` boucle `veille_cyber.py --intervalle $VEILLE_INTERVALLE` avec `VEILLE_DIR=/data/veille-cyber`.
- Fichiers : `/data/veille-cyber/rapports/AAAA-MM-JJ/HHhMM-<titre>.md`, `synthese-AAAA-MM-JJ.md`, `etat.json`, `veille.log`.
- Un passage ponctuel : `python /app/veille-cyber/veille_cyber.py --once`.

### Actions de la Console

| Action | Effet |
|---|---|
| Passage veille RSS maintenant | `veille_cyber.py --once` |
| WATCHTOWER · collecte flux / CISA KEV / NVD | `POST /run/fetch`, `/run/kev`, `/run/nvd` |
| WATCHTOWER · rapport quotidien / hebdo | `POST /run/daily`, `/run/weekly` |

Les tâches WATCHTOWER sont asynchrones : la Console affiche `{"started": "..."}` ; le résultat apparaît dans les rapports et `/health`.

---

## 5.4 Bug Bounty Lab

Environnement **cloisonné** (aucun secret ni socket Docker monté, `cap_drop: ALL`, `no-new-privileges`, périmètre en lecture seule ; il reste néanmoins sur le réseau Docker `justice` et peut joindre les autres services) pour tests de sécurité **sur des cibles explicitement autorisées**. Le conteneur reste actif (`stdin_open`, `tty`) ; on y entre avec `docker exec`.

Outils : ProjectDiscovery (subfinder, httpx, dnsx, naabu, nuclei, katana, uncover), recon (assetfinder, gau, hakrawler, gospider, waybackurls, anew, qsreplace), web (ffuf, gobuster, feroxbuster, nikto, whatweb, arjun, dalfox), réseau (nmap, masscan, dnsutils, whois, netcat), AppSec (semgrep, trufflehog, detect-secrets, sqlmap, testssl.sh), listes SecLists. Sur ARM64, les paquets APT optionnels absents sont ignorés au build.

### Garde-fous

- `scope-guard` lit `/scope/targets.json` (`config/bug-bounty/targets.json`) : une cible doit correspondre à `allow` (domaine, sous-domaine ou CIDR) et ne pas figurer dans `exclude`, sinon **BLOCKED**. Sans fichier valide, tout est refusé.
- Mode `--lab` : n'autorise que des hôtes privés/locaux (RFC1918, loopback, `.local`, `.lan`, `.test`, `.internal`, `.home`).
- `bb-run <outil> args…` vérifie chaque cible puis journalise la commande dans `/results/command-audit.log`.
- Le garde-fou est une sécurité, **pas une autorisation** : respectez les règles du programme (cadence, tests actifs interdits…).

### Utilisation

```bash
docker exec -it justice-league-bug-bounty bash
bb-pipeline.sh exemple.com passive               # reconnaissance passive (profil authorized)
bb-pipeline.sh exemple.com active                # + nuclei -safe et dalfox ; programmes qui l'autorisent
bb-pipeline.sh 192.168.1.20 passive lab          # cible de laboratoire privée
bb-run subfinder -d exemple.com                  # un outil, avec contrôle de périmètre
```

Le pipeline (7 étapes) : sous-domaines → DNS → surface HTTP → crawl → historique d'URL (gau) → [actif] nuclei → [actif] dalfox. Résultats dans `/results/<cible>/` (volume `bug_bounty_results`). Gabarits de rapport : `/opt/templates/BUG-REPORT.md` et `EVIDENCE.md`. Conservez les preuves et masquez secrets/données personnelles.
