# WATCHTOWER — veille cyber automatisée (V11)

Conteneur Python permanent (`justice-league-watchtower`) qui collecte, trie et résume l'actualité cyber.

```text
 RSS/Atom (CERT-FR, CISA, BleepingComputer, Krebs, Talos, ...)  ─┐
 CISA KEV (vulnérabilités exploitées activement)                 ├─> déduplication + score + thèmes
 NVD (nouvelles CVE à fort CVSS ou liées à votre watchlist)     ─┘          │
                                                                            ├─> SQLite (/data) + rapports MD/HTML
                                                                            ├─> MARTIAN  (/memory/entity, type "veille")
                                                                            └─> GREEN LANTERN (alertes + rapport dispo)
```

## Déploiement

```bash
./scripts/deploy-v11.sh      # build + démarrage, ajoute les variables WATCH_* à config.env
./scripts/verify-v11.sh
```

Interface : `http://127.0.0.1:8830` (localhost uniquement, comme le reste du SOC ; passer par WireGuard/SSH pour y accéder à distance).

## Ce qu'il fait

- **Collecte** : flux toutes les 30 min, KEV toutes les 6 h, NVD toutes les 2 h (sans clé API, c'est suffisant).
- **Premier cycle silencieux** : l'historique initial est ingéré sans déclencher d'alertes.
- **Score 0-100** : mots-clés de gravité (zero-day, exploitation active, RCE, ransomware...), poids de la source, présence dans la KEV (+50), correspondance avec votre watchlist (+25 par mot-clé).
- **Alertes** : un élément dont le score atteint `WATCH_ALERT_MIN_SCORE` (80) est envoyé via GREEN LANTERN (Discord/WhatsApp, `NOTIFY_DRY_RUN=NO` pour l'activer réellement).
- **Rapports** : quotidien à 07h30 (Europe/Paris) et hebdomadaire le lundi, dans `/data/reports/AAAA-MM-JJ-daily|weekly.md|html`.
- **Synthèse IA** (optionnelle, `WATCH_AI_SUMMARY=YES`) : Ollama résume uniquement les titres fournis ; elle est marquée « à vérifier ».

## Configuration

`config/watchtower/feeds.json` (copié depuis `feeds.example.json` au premier déploiement) contient les flux (nom, URL, poids) et la **watchlist** : adaptez-la à votre parc (technologies que vous exploitez ou auditez). Redémarrer n'est pas nécessaire : le fichier est relu à chaque cycle.

L'état de chaque flux est visible sur `/health` (`feeds_errors`). Un flux en erreur n'arrête pas les autres.

## API

| Route | Description |
|---|---|
| `GET /` | tableau de bord + liste des rapports |
| `GET /health` | état, dernier cycle, flux en erreur |
| `GET /items?hours=24&min_score=50&q=wazuh` | éléments filtrés (JSON) |
| `GET /reports` · `GET /reports/{nom}` | liste / lecture des rapports |
| `POST /run/{fetch\|nvd\|kev\|daily\|weekly}` | déclenche une tâche (en-tête `X-AI-Gateway-Token`) |

Exemple : `curl -X POST -H "X-AI-Gateway-Token: $AI_GATEWAY_TOKEN" http://127.0.0.1:8830/run/daily`

## Sécurité

Utilisateur non-root, système de fichiers en lecture seule (hors volume `/data`), `cap_drop: ALL`, `no-new-privileges`, port lié à 127.0.0.1, POST protégés par jeton, nom de rapport validé (pas de traversée de chemin), contenu des flux nettoyé/échappé et liens limités à http(s).

## Limites

Le score est heuristique et sert à trier, pas à décider. ORACLE (V8) continue de tourner en parallèle ; WATCHTOWER le complète et peut le remplacer à terme.
