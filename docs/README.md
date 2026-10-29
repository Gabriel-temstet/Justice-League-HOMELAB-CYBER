# Justice League Homelab — Documentation (Version Z)

Plateforme **SOC / veille cyber / OSINT / audit réseau** auto-hébergée, orchestrée par Docker Compose, pilotée depuis une **console web** et un script unique (`justice.sh`). Fonctionne sur Linux (amd64, arm64) et macOS (Intel, Apple Silicon M1–M4).

> Principe directeur : **l'IA analyse et propose, l'humain décide.** Aucune action sensible n'est déclenchée automatiquement.

## Sommaire

| # | Document | Pour qui / pour quoi |
|---|---|---|
| 1 | [Installation](01-installation.md) | Prérequis, installation Linux et macOS (M2), premier démarrage, mise à jour, désinstallation |
| 2 | [Configuration](02-configuration.md) | Toutes les variables de `config.env`, fichiers de configuration, secrets |
| 3 | [Architecture](03-architecture.md) | Services, flux de données, ports, volumes, réseaux, base de données |
| 4 | [Console web](04-console.md) | Guide utilisateur de la Justice League Console (Portainer-like + outils) |
| 5 | [Outils intégrés](05-outils-integres.md) | Scanner de ports, OSINT passif, veille cyber, Bug Bounty Lab |
| 6 | [Référence des API](06-reference-api.md) | Endpoints de MARTIAN, BATMAN, GREEN LANTERN, WATCHTOWER, SOC, Console |
| 7 | [Exploitation](07-exploitation.md) | `justice.sh`, supervision, sauvegarde/restauration, mises à jour, maintenance |
| 8 | [Sécurité](08-securite.md) | Modèle de menace, durcissement, cadre légal, bonnes pratiques |
| 9 | [Dépannage](09-depannage.md) | Problèmes fréquents (Linux, macOS ARM64) et solutions |
| 10 | [Développement](10-developpement.md) | Structure du dépôt, ajouter un outil/service, conventions, tests |

## Démarrage en 5 minutes

```bash
cd justice-league-homelab-z
cp config/config.env.example config/config.env   # remplacer TOUS les CHANGE_ME (voir 02-configuration.md)
chmod +x justice.sh
./justice.sh doctor      # diagnostic de la machine et de Docker
./justice.sh deploy      # construit et démarre toute la stack
open http://127.0.0.1:8801    # Console (macOS) — xdg-open sous Linux
```

## Glossaire des codenames

| Codename | Rôle | Conteneur |
|---|---|---|
| **MARTIAN-MANHUNTER** | Passerelle IA, mémoire d'enquête (PostgreSQL), corrélation | `martian-core`, `martian-db`, `martian-ollama` |
| **BATMAN** | Orchestration (n8n) et normalisation des événements | `batman-n8n`, `batman-postgres`, `batman-normalizer` |
| **COLLECTORS** | Lecture des journaux Suricata / Zeek / Wazuh | `justice-league-collectors` |
| **ORACLE** | Renseignement sur les menaces (CTI, flux RSS) + OSINT passif | `oracle-cti` |
| **GREEN ARROW** | Découverte d'actifs et scanner de ports | `green-arrow` |
| **GREEN LANTERN** | Notifications Discord / WhatsApp | `green-lantern` |
| **SOC COMMAND CENTER** | Tableau de bord SOC, dossiers, assistant IA | `justice-league-soc` |
| **WATCHTOWER** | Veille cyber automatisée (RSS, CVE NVD, CISA KEV) | `justice-league-watchtower` |
| **BUG BOUNTY LAB** | Environnement isolé pour tests autorisés | `justice-league-bug-bounty` |
| **CADDY** | Proxy TLS local devant le SOC | `justice-league-caddy` |
| **CONSOLE** | Gestion Docker + lancement des outils | `justice-league-container-manager` |

## Périmètre et état du projet

- Une seule version active (« Z ») : `docker/docker-compose.yml`, `justice.sh`, la Console. Les anciennes variantes V3–V11 sont archivées dans `archive/legacy/` à titre de référence uniquement.
- `ARCHITECTURE.md` (racine) décrit l'**infrastructure réseau cible** (Wazuh, Zeek/Suricata, VLAN…) ; le compose fourni déploie la partie logicielle de la plateforme et consomme les journaux de ces sondes (voir [Architecture](03-architecture.md)).
- Les images ARM64/amd64 sont multi-architecture. Voir [Installation](01-installation.md#compatibilité-processeurs) pour ce qui est vérifié et ce qui reste à confirmer au premier déploiement.

## Avertissement

Les outils de scan et de reconnaissance fournis doivent être utilisés **uniquement sur des systèmes que vous possédez ou pour lesquels vous avez une autorisation écrite**. Voir [Sécurité](08-securite.md#cadre-légal).
