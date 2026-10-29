# 3. Architecture

## Vue d'ensemble

La plateforme est une composition Docker unique (`docker/docker-compose.yml`) de 15 conteneurs sur un réseau bridge `justice`. Les services dialoguent par nom DNS Docker ; seuls quelques ports sont publiés, **tous liés à `127.0.0.1`**.

```mermaid
flowchart LR
  subgraph Sources
    SUR[Suricata eve.json]; ZEEK[Zeek conn.log.json]; WAZ[Wazuh alerts.json]
    RSS[Flux RSS CERT-FR / CISA / ...]; NVD[NVD + CISA KEV]; DOM[Domaines OSINT]
  end
  COL[COLLECTORS] --> MART
  SUR --> COL; ZEEK --> COL; WAZ --> COL
  RSS --> ORA[ORACLE CTI + OSINT]; DOM --> ORA; ORA --> MART
  GA[GREEN ARROW scanner] --> MART
  MART[MARTIAN-MANHUNTER<br/>martian-core + PostgreSQL] <--> OLL[Ollama IA locale]
  BAT[BATMAN n8n + normalizer] <--> MART
  MART --> SOC[SOC COMMAND CENTER]
  CAD[Caddy TLS :8443] --> SOC
  RSS --> WT[WATCHTOWER]; NVD --> WT
  COL --> GL[GREEN LANTERN]; WT --> GL; GL --> DIS[Discord / WhatsApp]
  CON[CONSOLE :8801] -. docker.sock .-> ALL((Tous les conteneurs))
  CON -. docker exec liste blanche .-> GA & ORA & WT
```

## Services

| Conteneur | Image / build | Rôle | Dépend de | Ports hôte |
|---|---|---|---|---|
| `martian-db` | `postgres:16-alpine` | Base mémoire MARTIAN | — | — |
| `martian-ollama` | `ollama/ollama` (profil `ollama`) | IA locale | — | — |
| `martian-core` | `./martian-core` (FastAPI) | Ingestion, mémoire, corrélation, enquêtes, interprétation IA | `martian-db` (healthy), Ollama (optionnel) | — (interne `:8787`) |
| `batman-postgres` | `postgres:17-alpine` | Base de n8n | — | — |
| `batman-n8n` | `n8nio/n8n` | Orchestration/automatisation | `batman-postgres` | `127.0.0.1:5678` |
| `batman-normalizer` | `./batman` | Normalise les événements vers MARTIAN | `martian-core` | — |
| `green-lantern` | `./notify` | Notifications | — | — (interne `:8898`) |
| `justice-league-collectors` | `./collectors` | Lit les journaux de sondes → MARTIAN, notifie les événements high/critical | `martian-core` | — |
| `oracle-cti` | `./oracle` | Flux CTI → MARTIAN ; OSINT passif | `martian-core` | — |
| `green-arrow` | `./green-arrow` (nmap, scapy, psutil) | Découverte d'actifs, audits de ports | `martian-core` | — |
| `justice-league-soc` | `./v8-api` | Tableau de bord SOC, dossiers, assistant IA | `martian-db`, `martian-core` | — (interne `:8810`) |
| `justice-league-caddy` | `caddy:2-alpine` | Proxy TLS devant le SOC | SOC (healthy) | `127.0.0.1:8443` |
| `justice-league-watchtower` | `./watchtower` | Veille cyber + API | — | `127.0.0.1:8830` |
| `justice-league-bug-bounty` | `./bug-bounty` | Lab d'outils offensifs encadré | — | — |
| `justice-league-container-manager` | `./container-manager` | Console web | — | `127.0.0.1:8801` |

L'API de MARTIAN (`:8787`) n'est **pas publiée** sur l'hôte : `./justice.sh verify` l'indique comme « non disponible » depuis l'hôte, ce qui est normal. Pour l'interroger : `docker exec justice-league-soc python -c "import urllib.request;print(urllib.request.urlopen('http://martian-core:8787/health').read())"`.

## Flux de données

### 1. Événements de sécurité (chemin SOC)

```
Suricata/Zeek/Wazuh (fichiers JSON)
  → COLLECTORS : lecture incrémentale, normalisation (source, event_type, severity, indicators…)
  → MARTIAN POST /ingest : stockage de l'événement, entités « indicator », relations
  → si severity ∈ {high, critical} :
        MARTIAN POST /investigations  (ouverture d'une enquête)
        GREEN LANTERN POST /notify    (Discord / WhatsApp)
```

BATMAN (n8n) peut orchestrer un flux plus riche : réception → normalisation (`/normalize`) → ingestion → enrichissement (actifs, CVE, CTI, historique) → `POST /correlate` → digest ou enquête + notification. Le workflow d'exemple est dans `docker/batman/justice-league-v7-soc-workflow.json` (à importer dans n8n). **Aucune remédiation n'est exécutée automatiquement** : `human_approval_required` vaut `true` dès `high`.

### 2. Renseignement et veille

- **ORACLE** lit `CTI_FEEDS` toutes les `CTI_INTERVAL` s, dédoublonne (SQLite `/data/oracle.db`) et envoie chaque nouvel élément à MARTIAN (`entity_type=cti`).
- **ORACLE OSINT** (`osint_veille.py`) : DNS, sous-domaines via Certificate Transparency, certificat TLS, en-têtes HTTP → rapports Markdown.
- **WATCHTOWER** : flux RSS pondérés + CISA KEV + NVD ; score 0–100 (sévérité, watchlist, KEV, CVSS) ; rapports quotidien/hebdo (Markdown + HTML) ; alertes ≥ `WATCH_ALERT_MIN_SCORE` ; pousse les éléments à MARTIAN.
- **veille_cyber.py** (intégré à WATCHTOWER) : second collecteur RSS qui produit un rapport Markdown par nouvelle.

### 3. Inventaire d'actifs

GREEN ARROW exécute `nmap -sn` sur `AUTHORIZED_CIDRS` toutes les `DISCOVERY_INTERVAL` s et enregistre chaque hôte comme entité `asset` dans MARTIAN. En parallèle, `run_audits.py` produit les CSV d'audit dans `/results`.

### 4. Pilotage

La **Console** parle au démon Docker via `/var/run/docker.sock` (gestion des conteneurs) et exécute des **commandes en liste blanche** dans GREEN ARROW, ORACLE et WATCHTOWER via `docker exec`. Voir [Console](04-console.md).

## Mémoire MARTIAN (PostgreSQL)

| Table | Contenu |
|---|---|
| `entities(entity_type, external_id, data, first_seen, last_seen)` | Actifs, indicateurs, éléments CTI |
| `events(event_type, source, severity, event_time, external_id, data)` | Événements normalisés |
| `relationships(left_type, left_id, relation, right_type, right_id, confidence, evidence)` | Graphe (ex. événement *affects* actif) |
| `investigations`, `investigation_events` | Enquêtes et leurs événements |
| `soc_cases`, `soc_case_events`, `soc_notes`, `soc_audit` | Dossiers, notes et journal d'audit du SOC (créés par `justice-league-soc`) |

Le modèle est orienté preuve : les observations sont conservées séparément de l'interprétation de l'IA, ce qui rend les enquêtes reproductibles et auditables.

## Réseau et exposition

| Port hôte | Service | Exposition |
|---|---|---|
| 8801 | Console | `127.0.0.1` uniquement |
| 8443 | SOC via Caddy (TLS interne) | `127.0.0.1` uniquement |
| 8830 | WATCHTOWER | `127.0.0.1` uniquement |
| 5678 | n8n | `127.0.0.1` uniquement |

Pour un accès distant, utilisez un VPN ou un tunnel SSH : `ssh -L 8801:127.0.0.1:8801 utilisateur@serveur`. **Ne publiez jamais** ces ports sur Internet.

## Durcissement des conteneurs

| Conteneur | Mesures |
|---|---|
| WATCHTOWER | utilisateur non-root (65532), système de fichiers en lecture seule, `cap_drop: ALL`, `no-new-privileges` |
| Console | système de fichiers en lecture seule, `cap_drop: ALL`, `no-new-privileges` (monte le socket Docker : voir [Sécurité](08-securite.md)) |
| Bug Bounty Lab | `cap_drop: ALL`, `no-new-privileges`, périmètre en lecture seule |
| GREEN ARROW | `cap_add: NET_RAW` (ARP/scapy, nmap) |

## Architecture réseau cible (`ARCHITECTURE.md`)

Le fichier `ARCHITECTURE.md` décrit une infrastructure complète autour de la plateforme : périmètre (AQUAMAN), sondes réseau SPAN/TAP (FLASH : Zeek/IDS), Wazuh (CYBORG), VLAN de laboratoire isolé, etc. Ces éléments d'infrastructure **ne sont pas déployés par ce compose** ; ils alimentent la plateforme en déposant leurs journaux dans `LOG_ROOT`.

## Répertoire `archive/` et dossiers hérités

`archive/legacy/` (anciennes versions V3–V11 et scripts), `docker/compose.yml` (ébauche) et `docker/soc-command-center/` (ancienne image, remplacée par `docker/v8-api/`) sont conservés pour référence ; **ils ne sont pas utilisés** par la version Z.
