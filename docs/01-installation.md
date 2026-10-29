# 1. Installation

## Prérequis

| Élément | Minimum | Recommandé |
|---|---|---|
| Docker | Engine 24+ avec plugin **Compose v2.20 ou plus** (`docker compose version` ; requis pour `depends_on.required`) | Docker Engine 27+ / Docker Desktop récent |
| RAM allouée à Docker | 4 Go (sans Ollama) | 8 Go (avec Ollama + modèle 3B) |
| CPU | 2 cœurs | 4 cœurs |
| Disque | 15 Go | 30 Go (images, volumes, modèle IA, bug bounty) |
| Réseau sortant | HTTPS (flux RSS, NVD, CISA, registres d'images) | — |
| Shell | bash 3.2+ (macOS inclus) | — |

Systèmes supportés : **Linux** (Debian/Ubuntu/Fedora… amd64 ou arm64) et **macOS** Intel ou Apple Silicon (M1/M2/M3/M4) via Docker Desktop, OrbStack ou Colima.

## Compatibilité processeurs

| Architecture | Statut |
|---|---|
| amd64 (Intel, AMD) | Supporté. Console et scripts testés sur x86_64. |
| arm64 (Apple Silicon, Linux ARM, Raspberry Pi 5) | Supporté. Aucune option `platform:` ni émulateur : les images de base (`postgres`, `n8n`, `ollama`, `caddy`, `python`, `debian`) sont multi-architecture et toutes les dépendances Python ont des wheels `aarch64`. |

À confirmer au **premier déploiement** sur chaque architecture : disponibilité de certains paquets APT optionnels du Bug Bounty Lab (ignorés automatiquement s'ils manquent) et compilation des outils Go (`@latest`). La stack complète n'a pas été construite de bout en bout dans l'environnement de rédaction : si une étape échoue, consultez [Dépannage](09-depannage.md).

## Installation sur Linux

```bash
# 1. Docker (exemple Debian/Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"      # puis se reconnecter

# 2. Projet
unzip justice-league-homelab-z.zip && cd justice-league-homelab-z

# 3. Configuration
cp config/config.env.example config/config.env
nano config/config.env               # remplacer tous les CHANGE_ME (voir 02-configuration.md)

# 4. Vérifier puis déployer
chmod +x justice.sh
./justice.sh doctor
./justice.sh check
./justice.sh deploy
./justice.sh status
./justice.sh verify
```

## Installation sur macOS (Apple Silicon, ex. M2)

```bash
# 1. Docker Desktop pour Apple Silicon (ou OrbStack / Colima)
brew install --cask docker           # puis ouvrir Docker Desktop une fois
# Docker Desktop > Settings > Resources : Memory ≥ 6 Go (8 Go conseillés avec Ollama)

# 2. Projet
cd ~/justice-league-homelab-z
cp config/config.env.example config/config.env
open -e config/config.env            # remplacer tous les CHANGE_ME
chmod +x justice.sh
./justice.sh doctor
./justice.sh deploy
open http://127.0.0.1:8801
```

### Particularités macOS

- **IA locale plus rapide** : dans un conteneur, Ollama tourne sur CPU. Pour utiliser le GPU (Metal), installez Ollama nativement :
  ```bash
  brew install ollama && ollama serve &
  ollama pull llama3.2:3b
  ```
  puis dans `config/config.env` : `OLLAMA_URL=http://host.docker.internal:11434`. Avec cette valeur, `justice.sh` ne démarre pas le conteneur Ollama. Laissez vide pour garder le conteneur.
- **Scanner réseau** : Docker Desktop exécute les conteneurs dans une VM Linux ; GREEN ARROW voit le réseau de la VM, pas le LAN du Mac. Pour auditer le LAN, lancez les scripts natifs de `docker/green-arrow/tools/` (voir [Outils intégrés](05-outils-integres.md#utilisation-native-hors-docker)).
- **Journaux de sondes** : `LOG_ROOT` vaut `../data/logs` (dans le projet) ; `/srv` n'existe pas sur macOS.
- **Socket Docker** : `/var/run/docker.sock` fonctionne avec Docker Desktop et OrbStack. Avec Colima : `export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` ou créez le lien `/var/run/docker.sock`.

## Ce que fait `./justice.sh deploy`

1. `check` : refuse de démarrer si `config.env` manque ou contient `CHANGE_ME` pour `MARTIAN_DB_PASSWORD`, `BATMAN_DB_PASSWORD`, `AI_GATEWAY_TOKEN`, `N8N_ENCRYPTION_KEY`, `SOC_ADMIN_PASSWORD`, puis valide la syntaxe Compose.
2. Crée les dossiers nécessaires (journaux, configurations).
3. `docker compose up -d --build` avec le profil `ollama` si `OLLAMA_URL` est vide.

La première construction dure plusieurs minutes (images, outils Go du Bug Bounty Lab). Au premier démarrage avec le conteneur Ollama, **téléchargez le modèle** :

```bash
docker exec martian-ollama ollama pull llama3.2:3b     # ou la valeur de OLLAMA_MODEL
```

## Configuration post-installation (optionnelle)

```bash
# Flux et mots-clés de WATCHTOWER
cp config/watchtower/feeds.example.json config/watchtower/feeds.json

# Périmètre du Bug Bounty Lab (cibles AUTORISÉES uniquement)
cp config/bug-bounty/targets.example.json config/bug-bounty/targets.json
cp config/bug-bounty/program.example.json config/bug-bounty/program.json
```

Puis renseignez dans `config.env` : `AUTHORIZED_CIDRS` (scanner), `OSINT_DOMAINS` (OSINT), `DISCORD_WEBHOOK_URL` (notifications). Voir [Configuration](02-configuration.md).

## Points d'accès après déploiement

| Service | URL (liée à 127.0.0.1) | Authentification |
|---|---|---|
| **Console** | http://127.0.0.1:8801 | `SOC_ADMIN_USER` / `SOC_ADMIN_PASSWORD` (Basic Auth) |
| SOC Command Center (via Caddy, TLS auto-signé) | https://127.0.0.1:8443 | formulaire (mêmes identifiants) |
| WATCHTOWER | http://127.0.0.1:8830 | lecture libre en local ; `POST /run/*` nécessite le jeton |
| n8n (BATMAN) | http://127.0.0.1:5678 | compte créé au premier accès |

Le navigateur affiche un avertissement pour le certificat de Caddy (`tls internal`) : c'est normal en local.

## Mise à jour

```bash
# Sauvegarder d'abord (voir 07-exploitation.md)
./justice.sh backup
# Récupérer la nouvelle version du projet, conserver config/config.env, puis :
./justice.sh deploy          # reconstruit les images modifiées et recrée les conteneurs
```

Les images `latest` (n8n, ollama) sont rafraîchies avec `docker compose --env-file config/config.env -f docker/docker-compose.yml pull`. Pensez à figer des versions pour la production.

## Arrêt et désinstallation

```bash
./justice.sh stop                                  # arrête sans supprimer les données
# Suppression complète (IRRÉVERSIBLE : supprime les volumes = toutes les données)
docker compose --env-file config/config.env -f docker/docker-compose.yml --profile ollama down -v
```
