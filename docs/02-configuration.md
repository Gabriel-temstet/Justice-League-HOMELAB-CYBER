# 2. Configuration

Toute la configuration passe par **`config/config.env`** (copié depuis `config/config.env.example`, jamais versionné) et quelques fichiers JSON dans `config/`. Docker Compose lit `config.env` via `--env-file` (géré par `justice.sh`).

> Les valeurs `CHANGE_ME` sont **refusées** par `./justice.sh check`. Générez des secrets forts : `openssl rand -hex 32`.

## Secrets obligatoires

| Variable | Rôle |
|---|---|
| `MARTIAN_DB_PASSWORD` | Mot de passe PostgreSQL de MARTIAN (mémoire/enquêtes) |
| `BATMAN_DB_PASSWORD` | Mot de passe PostgreSQL de n8n |
| `AI_GATEWAY_TOKEN` | Jeton partagé entre services (en-tête `X-AI-Gateway-Token`) pour MARTIAN, WATCHTOWER, collecteurs… |
| `N8N_ENCRYPTION_KEY` | Clé de chiffrement des identifiants stockés dans n8n. **À conserver** : la perdre rend les identifiants n8n illisibles |
| `SOC_ADMIN_PASSWORD` | Mot de passe de la Console et du SOC Command Center |
| `SOC_ADMIN_USER` | Identifiant admin (défaut `admin`) |

## Général

| Variable | Défaut | Description |
|---|---|---|
| `TIMEZONE` | `Europe/Paris` | Fuseau horaire (n8n, WATCHTOWER : heures des rapports) |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modèle utilisé par MARTIAN, le SOC et WATCHTOWER |
| `OLLAMA_URL` | *(vide)* | Vide = conteneur Ollama (profil `ollama`). Sinon URL d'un Ollama externe, ex. `http://host.docker.internal:11434` (Ollama natif Mac) |
| `LOG_ROOT` | `../data/logs` | Dossier des journaux de sondes monté en lecture seule dans les collecteurs (relatif à `docker/`, ou chemin absolu). Créé par `justice.sh deploy` |
| `CONFIRM_INSTALL`, `SOC_BIND`, `SOC_PORT` | — | Hérités des anciennes versions, **non utilisés** par la version Z |

## Notifications (GREEN LANTERN)

| Variable | Défaut | Description |
|---|---|---|
| `NOTIFY_DRY_RUN` | `YES` | `YES` = rien n'est envoyé, le message est seulement renvoyé par l'API. Passez à `NO` pour envoyer réellement |
| `DISCORD_WEBHOOK_URL` | vide | URL de webhook Discord |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TO` | vides | API WhatsApp Cloud (Meta). Les trois doivent être renseignés |

## Collecteurs et ORACLE (CTI + OSINT)

| Variable | Défaut | Description |
|---|---|---|
| `COLLECTOR_INTERVAL` | `5` | Secondes entre deux lectures des fichiers de journaux |
| `CTI_FEEDS` | CERT-FR ; CISA | Flux RSS/Atom de l'ORACLE, séparés par `;` |
| `CTI_INTERVAL` | `900` | Secondes entre deux relevés CTI |
| `OSINT_DOMAINS` | vide | Domaines à surveiller en OSINT passif, séparés par virgule/point-virgule. **Uniquement vos domaines ou ceux de clients avec accord** |
| `OSINT_INTERVAL_HOURS` | `6` | Heures entre deux passages OSINT |

Les chemins lus par les collecteurs sont fixes dans le compose : `/logs/suricata/eve.json`, `/logs/zeek/conn.log.json`, `/logs/wazuh/alerts.json` (sous `LOG_ROOT`).

## Scanner de ports (GREEN ARROW)

| Variable | Défaut | Description |
|---|---|---|
| `AUTHORIZED_CIDRS` | vide | Sous-réseaux **autorisés**, séparés par des espaces (ex. `192.168.1.0/24 10.0.0.0/24`). Vide = découverte et scans réseau désactivés. Tout scan hors de cette liste est refusé par l'outil |
| `DISCOVERY_INTERVAL` | `3600` | Secondes entre deux découvertes `nmap -sn` (inventaire envoyé à MARTIAN) |
| `AUDIT_INTERVAL` | `86400` | Secondes entre deux cycles d'audit automatique (ports locaux + découverte ARP) |
| `SCAN_FULL_PORTS` | `NO` | `YES` = scan TCP complet (1–65535) de **chaque** machine découverte à chaque cycle. Bruyant, long : à n'activer que sur réseau autorisé |

## Veille cyber (WATCHTOWER)

| Variable | Défaut | Description |
|---|---|---|
| `WATCH_INTERVAL` | `1800` | Collecte des flux RSS (s) |
| `WATCH_NVD_INTERVAL` | `7200` | Interrogation NVD (s) |
| `WATCH_KEV_INTERVAL` | `21600` | Catalogue CISA KEV (s) |
| `WATCH_REPORT_HOUR` / `WATCH_REPORT_MINUTE` | `7` / `30` | Heure du rapport quotidien |
| `WATCH_WEEKLY_DAY` | `0` | Jour du rapport hebdo (0 = lundi) |
| `WATCH_ALERT_MIN_SCORE` | `80` | Score (0–100) minimal pour déclencher une alerte |
| `WATCH_NOTIFY` | `YES` | Envoie les alertes via GREEN LANTERN |
| `WATCH_AI_SUMMARY` | `NO` | Résumés IA via Ollama (plus lent) |
| `WATCH_KEYWORDS` | vide | Mots-clés de votre parc, séparés par virgule (ajoutés à la *watchlist*) |
| `WATCH_RETENTION_DAYS` | `180` | Rétention des éléments |
| `NVD_MIN_CVSS` | `8.0` | Score CVSS minimal retenu depuis NVD |
| `NVD_API_KEY` | vide | Clé API NVD (augmente les quotas) |
| `VEILLE_INTERVALLE` | `1800` | Intervalle (s) du script `veille_cyber.py` intégré |

## Fichiers de configuration

| Fichier | Rôle |
|---|---|
| `config/config.env` | Variables ci-dessus (secrets, non versionné) |
| `config/watchtower/feeds.json` | Flux RSS (nom, URL, poids) et *watchlist* de produits. Modèle : `feeds.example.json`. Absent = flux par défaut. Monté en lecture seule dans `/config` |
| `config/bug-bounty/targets.json` | Périmètre **autorisé** (`allow`, `exclude`) lu par `scope-guard`. Modèle : `targets.example.json` |
| `config/bug-bounty/program.json` | Règles du programme (cadence, tests actifs). Modèle : `program.example.json` |
| `docker/caddy/Caddyfile` | Proxy TLS : `:8443 { tls internal; reverse_proxy soc-command-center:8810 }` |

### Exemple `feeds.json`

```json
{
  "feeds": [
    {"name": "CERT-FR", "url": "https://www.cert.ssi.gouv.fr/feed/", "weight": 20}
  ],
  "watchlist": ["proxmox", "wazuh", "fortinet", "openssh"]
}
```

Le `weight` est un score de base ajouté aux éléments du flux ; chaque mot de la `watchlist` trouvé ajoute des points (plafonné). Rechargé à chaque collecte, sans redémarrage.

### Exemple `targets.json` (Bug Bounty Lab)

```json
{
  "allow": ["example.com", "*.example.com", "192.0.2.0/24"],
  "exclude": ["admin.example.com"],
  "notes": "Cibles explicitement autorisées par le programme."
}
```

## Volumes Docker

| Volume | Contenu | Sauvegardé par `backup` |
|---|---|---|
| `martian_db` | Base MARTIAN (événements, entités, enquêtes, dossiers SOC) | Oui (`pg_dump`) |
| `batman_db` | Base n8n | Oui (`pg_dump`) |
| `n8n` | Données n8n (workflows exportables, identifiants chiffrés) | Non — exporter les workflows |
| `ollama` | Modèles IA téléchargés | Non (re-téléchargeables) |
| `caddy_data`, `caddy_config` | Certificat local Caddy | Non |
| `oracle_data` | Base SQLite CTI + `home/veille-osint` (OSINT) | Non |
| `watchtower_data` | Base, rapports WATCHTOWER, `veille-cyber/` | Non |
| `green_arrow_results` | CSV du scanner (`/results`) | Non |
| `bug_bounty_workspace`, `bug_bounty_results` | Espace de travail et résultats du lab | Non |

Voir [Exploitation](07-exploitation.md#sauvegarde-et-restauration) pour sauvegarder les volumes non couverts.
