# 6. Référence des API

Sauf mention contraire, les API internes sont accessibles **depuis le réseau Docker** (ex. `http://martian-core:8787`). Les ports publiés sur l'hôte sont listés dans [Architecture](03-architecture.md#réseau-et-exposition).

Authentification inter-services : en-tête **`X-AI-Gateway-Token: <AI_GATEWAY_TOKEN>`**.

## MARTIAN-MANHUNTER — `martian-core:8787`

| Méthode | Chemin | Auth | Description |
|---|---|---|---|
| GET | `/health` | non | État du service |
| POST | `/memory/entity` | jeton | Crée/met à jour une entité `{entity_type, external_id, data}` |
| POST | `/memory/event` | jeton | Enregistre un événement brut |
| GET | `/memory/events` | jeton | Liste des événements |
| GET | `/memory/search` | jeton | Recherche dans la mémoire |
| GET | `/memory/entity/{entity_type}/{external_id}` | jeton | Lit une entité |
| POST | `/ingest` | jeton | Ingère un événement **normalisé** (voir ci-dessous) |
| POST | `/correlate` | jeton | Corrèle une alerte avec actifs/CVE/CTI/historique |
| GET | `/investigations` | jeton | Liste (`limit` ≤ 500, `status`) |
| POST | `/investigations` | jeton | Ouvre une enquête `{title, query, priority}` |
| GET | `/investigations/{id}` | jeton | Détail |
| PATCH | `/investigations/{id}` | jeton | Met à jour `status`, `priority`, `summary` |

> Si `AI_GATEWAY_TOKEN` est vide côté service, l'authentification est désactivée : `justice.sh check` impose donc une valeur.

### `POST /ingest`

```json
{
  "source": "suricata",
  "event_type": "alert",
  "severity": "high",
  "timestamp": "2026-10-29T08:00:00Z",
  "external_id": "suricata:abc123",
  "asset_ids": ["10.10.20.25"],
  "indicators": ["203.0.113.10", "malware.example"],
  "data": {"signature": "ET MALWARE …"}
}
```
`severity` ∈ `info|low|medium|high|critical`. Réponse : `{"status":"ingested","event":{…}}`. Crée les relations *event → affects → asset* et *event → contains → indicator*.

### `POST /correlate`

Entrée : `{alert, assets[], cves[], cti[], history[], ask_ai}` (exemple : `correlation-example.json`). Sortie :

```json
{
  "matches": [{"type":"alert_to_asset","asset":"WIN-01","evidence":["10.10.20.25"]}],
  "correlation_score": 60,
  "severity": "high",
  "human_approval_required": true,
  "ai_assessment": {}
}
```
Score = 20 points par correspondance (+20 si historique) plafonné à 100 ; `critical` ≥ 80, `high` ≥ 60, `medium` ≥ 30. `ai_assessment` n'est présent que si `ask_ai` est vrai ; en cas d'indisponibilité d'Ollama : `{"error":"AI interpretation unavailable"}`.

## BATMAN normalizer — `batman-normalizer`

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/health` | État |
| POST | `/normalize?source=…&forward=true` | **Jeton.** Normalise un événement brut (corps JSON libre : Wazuh/Zeek/Suricata) ; avec `forward=true` (défaut) l'envoie à MARTIAN `/ingest` et renvoie `{normalized, martian}`, sinon renvoie seulement l'événement normalisé |

## GREEN LANTERN — `green-lantern:8898`

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/health` | `{status, discord, whatsapp, dry_run}` |
| POST | `/notify` | `{title, body, severity}`. En `NOTIFY_DRY_RUN=YES` : renvoie `{"status":"dry_run", …}` sans rien envoyer |

## WATCHTOWER — `127.0.0.1:8830`

| Méthode | Chemin | Auth | Description |
|---|---|---|---|
| GET | `/` | non | Page HTML : éléments récents, rapports |
| GET | `/health` | non | Compteurs, dernières collectes, flux OK/en erreur |
| GET | `/items` | non | Éléments : `hours` (24), `min_score` (0), `q`, `limit` (≤ 500) |
| GET | `/reports` | non | Noms des rapports (`AAAA-MM-JJ-daily|weekly.md|html`) |
| GET | `/reports/{name}` | non | Contenu d'un rapport |
| POST | `/run/{task}` | **jeton** | `task` ∈ `fetch`, `nvd`, `kev`, `daily`, `weekly` ; renvoie `{"started": task}` |

Exemple :
```bash
curl -X POST -H "X-AI-Gateway-Token: $AI_GATEWAY_TOKEN" http://127.0.0.1:8830/run/daily
curl "http://127.0.0.1:8830/items?hours=48&min_score=60&q=fortinet"
```

## SOC COMMAND CENTER — `justice-league-soc:8810` (via Caddy `https://127.0.0.1:8443`)

Authentification par session : `POST /api/login {user, password}` pose un cookie `soc_session` (HttpOnly, SameSite strict, 8 h).

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/health` | État |
| POST | `/api/login`, `/api/logout` | Session |
| GET | `/api/overview` | Compteurs (événements 24 h, high/critical, enquêtes ouvertes, dossiers, actifs, indicateurs, sources) |
| GET | `/api/events`, `/api/search` | Événements, recherche |
| GET/POST | `/api/cases` | Dossiers SOC |
| GET | `/api/cases/{id}` | Détail d'un dossier |
| POST | `/api/cases/{id}/events` | Rattache un événement `{event_id}` |
| POST | `/api/cases/{id}/notes` | Ajoute une note `{body}` |
| GET | `/api/graph` | Graphe entités/relations |
| GET | `/api/audit` | Journal d'audit (`limit` ≤ 500) |
| POST | `/api/ask` | Question `{question}` : recherche d'indices dans la base puis réponse IA fondée uniquement sur ces indices ; la question est auditée |

## Console — `127.0.0.1:8801`

Authentification Basic ; les requêtes non-GET exigent `X-JLC: 1`. Exemples :

```bash
curl -u admin:MOT_DE_PASSE http://127.0.0.1:8801/api/containers
curl -u admin:MOT_DE_PASSE -X POST -H 'X-JLC: 1' -H 'Content-Type: application/json' \
     -d '{"action":"restart"}' http://127.0.0.1:8801/api/containers/green-arrow/action
```

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/health` | État (sans authentification) |
| GET | `/api/overview` | Hôte, compteurs, usage CPU/mémoire/réseau |
| GET | `/api/containers` | Liste avec statistiques (`stats=false` pour les omettre) |
| GET | `/api/containers/{nom}` | Détail (env avec secrets masqués, volumes, réseaux…) |
| POST | `/api/containers/{nom}/action` | `{"action": "start|stop|restart|pause|unpause"}` |
| GET | `/api/containers/{nom}/logs` | `tail` (≤ 2000), `since` |
| GET | `/api/images`, `/api/volumes`, `/api/networks` | Inventaires |
| GET | `/api/tools` | Catalogue des outils, état, périmètres |
| GET | `/api/tools/{outil}/options/{source}` | Options dynamiques (`cidrs`, `domains`) |
| POST | `/api/tools/{outil}/{action}` | `{"params": {…}}` → tâche `{id, status…}` ; 409 si déjà en cours |
| GET | `/api/jobs`, `/api/jobs/{id}?since=N` | Tâches et sortie incrémentale |
| GET | `/api/tools/{outil}/files?root=&path=` | Liste d'un dossier |
| GET | `/api/tools/{outil}/file?root=&path=[&download=1]` | Aperçu ou téléchargement |

Codes d'erreur : 400 paramètre invalide, 401 non authentifié, 403 CSRF, 404 introuvable, 409 conflit/conteneur arrêté, 429 trop de tentatives, 503 Docker indisponible.
