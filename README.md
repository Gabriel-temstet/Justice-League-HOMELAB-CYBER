# Justice League Homelab

> 📚 **Documentation complète : [`docs/`](docs/README.md)** — installation (Linux, macOS Apple Silicon), configuration, architecture, console, outils, API, exploitation, sécurité, dépannage, développement.

**Une seule version active.** Les évolutions sont intégrées dans `docker/docker-compose.yml`, `justice.sh` et le gestionnaire web. Les anciennes variantes V3–V11 ne sont plus nécessaires au déploiement ; les fichiers historiques restent dans `archive/legacy/` à titre de référence.

## Console web (gestion Docker + outils intégrés)

La **Justice League Console** remplace le simple gestionnaire : `http://127.0.0.1:8801` (identifiants `SOC_ADMIN_USER` / `SOC_ADMIN_PASSWORD`).

- **Tableau de bord** : CPU / mémoire / réseau en direct, état de la stack par codename, alertes (unhealthy, redémarrages en boucle, arrêts en erreur).
- **Conteneurs** : filtre, tri, CPU/mémoire par conteneur, démarrer / arrêter / redémarrer / pause, tiroir de détail (santé, volumes, réseaux, durcissement, variables avec secrets masqués) et journaux en direct filtrables.
- **Outils** : lancement en un clic des outils intégrés avec sortie en direct, puis navigation / aperçu / téléchargement des rapports (CSV rendus en tableau) :
  - GREEN ARROW : audit ports locaux, découverte ARP, nmap, scan TCP complet (cibles limitées à `AUTHORIZED_CIDRS`) ;
  - ORACLE : OSINT passif, ajout/retrait de domaines, passage immédiat ;
  - WATCHTOWER : passage de veille, collecte flux / KEV / NVD, rapports quotidien et hebdomadaire.
- **Tâches** : historique des actions d'outils. **Images / Volumes / Réseaux** : inventaire en lecture seule.

Sécurité : lié à `127.0.0.1` (VPN ou tunnel SSH pour l'accès distant), Basic Auth avec limitation des tentatives, protection CSRF, en-têtes CSP, journal d'audit (`docker logs justice-league-container-manager`). **Aucune exécution de commande arbitraire** : seules les commandes en liste blanche de `docker/container-manager/tools.py` sont exécutables, avec paramètres validés. Pour ajouter un outil, ajoutez une entrée dans ce catalogue.

> Le socket Docker équivaut à un accès administrateur à l'hôte : ne publiez jamais ce port sur Internet et utilisez un mot de passe fort et unique.

## Plateformes supportées (Linux amd64, Linux arm64, macOS Apple Silicon M1/M2/M3/M4)

Toutes les images utilisées sont multi-architecture (`postgres`, `n8n`, `ollama`, `caddy`, `python`, `debian`) et les dépendances Python disposent de wheels `aarch64` : **aucun émulateur (Rosetta/QEMU) ni option `platform:`** n'est nécessaire, les images se construisent nativement en ARM64.

### Installation sur Mac (puce M2 ou autre Apple Silicon)

```bash
# 1. Docker : Docker Desktop (Apple Silicon), OrbStack ou Colima
brew install --cask docker          # puis lancer Docker Desktop une première fois
# Alloue au moins 6 Go de RAM à Docker (Settings > Resources) ; 8 Go conseillés avec Ollama

# 2. Récupérer le projet puis configurer
cd justice-league-homelab-z
cp config/config.env.example config/config.env   # remplace tous les CHANGE_ME
chmod +x justice.sh
./justice.sh doctor      # diagnostic : architecture, ressources, Docker, IA
./justice.sh deploy
open http://127.0.0.1:8801   # Console
```

Points propres à macOS :

- **IA locale plus rapide (recommandé)** : dans un conteneur, Ollama ne peut pas utiliser le GPU du Mac (Metal) et tourne sur CPU. Installez-le nativement (`brew install ollama && ollama serve && ollama pull llama3.2:3b`) puis mettez `OLLAMA_URL=http://host.docker.internal:11434` dans `config/config.env` : `justice.sh` n'active alors pas le conteneur Ollama.
- **Scanner réseau (GREEN ARROW)** : Docker Desktop fait tourner les conteneurs dans une VM Linux. La découverte ARP et les scans voient donc le réseau de la VM, pas le LAN du Mac, et l'audit « ports locaux » décrit le conteneur. Pour auditer votre LAN depuis le Mac, utilisez directement les scripts natifs (`docker/green-arrow/tools/`, `python3 audit_reseau_machine_distante.py` avec `sudo`) : ils fonctionnent sur macOS.
- **Journaux Suricata/Zeek/Wazuh** : `LOG_ROOT` vaut par défaut `data/logs` dans le projet (créé automatiquement) ; `/srv` n'existe pas sur macOS.
- **Socket Docker de la Console** : `/var/run/docker.sock` fonctionne avec Docker Desktop et OrbStack ; avec Colima, exportez `DOCKER_HOST` ou créez le lien `/var/run/docker.sock`.
- **Bug Bounty Lab** : certains outils APT optionnels peuvent ne pas exister pour ARM64 ; ils sont alors ignorés pendant la construction (message `[bug-bounty] paquet … indisponible`), les outils Go (subfinder, httpx, nuclei…) sont compilés nativement.
- La première construction (images + outils Go) prend plusieurs minutes.

## Démarrage

Prérequis : Docker Engine et le plugin Docker Compose.

```bash
cp config/config.env.example config/config.env
# Modifie config/config.env : mots de passe et jetons uniques, jamais CHANGE_ME.
chmod +x justice.sh
./justice.sh check
./justice.sh deploy
./justice.sh status
./justice.sh verify
```

Interface principale du SOC : selon la configuration, `https://127.0.0.1:8443`.
Gestionnaire de conteneurs : `http://127.0.0.1:8801`.

## Commandes unifiées

| Commande | Action |
|---|---|
| `./justice.sh check` | Valide les secrets requis et la configuration Compose |
| `./justice.sh deploy` | Construit et démarre la stack complète |
| `./justice.sh status` | Liste l'état des services |
| `./justice.sh verify` | Vérifie les endpoints principaux |
| `./justice.sh logs` | Suit les journaux |
| `./justice.sh stop` | Arrête la stack sans supprimer les données |
| `./justice.sh backup` | Exporte les bases MARTIAN et BATMAN et les configurations de veille |

Toute nouvelle fonctionnalité doit être intégrée à cette version Z, sans créer une nouvelle série de scripts versionnés.

## Services inclus

- MARTIAN-MANHUNTER : passerelle IA et corrélation SOC
- PostgreSQL MARTIAN et BATMAN
- BATMAN / n8n : orchestration
- Collecteurs, ORACLE CTI et GREEN ARROW
- GREEN LANTERN : notifications
- SOC Command Center
- WATCHTOWER : veille cyber
- Bug Bounty Lab : environnement isolé pour cibles autorisées
- Caddy : proxy local TLS
- Container Manager : interface web Docker

## Sécurité opérationnelle

- L'IA analyse et propose ; elle ne déclenche pas automatiquement les actions sensibles.
- Le gestionnaire expose uniquement les opérations Docker explicites `start`, `stop`, `restart` et la lecture des journaux. Il n'offre pas d'exécution arbitraire de commandes dans les conteneurs.
- Le laboratoire de bug bounty doit être utilisé uniquement sur des actifs autorisés et selon le périmètre configuré.
- N'expose pas directement Docker, Proxmox, n8n, Wazuh, Grafana ou les passerelles IA à Internet.
- Teste les sauvegardes et conserve une copie hors de l'hôte.

## Structure canonique

- `docker/docker-compose.yml` : stack complète unique
- `justice.sh` : point d'entrée opérationnel unique
- `docker/container-manager/` : interface de gestion web
- `config/config.env` : configuration locale et secrets (non versionnés)
