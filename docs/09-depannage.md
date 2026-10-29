# 9. Dépannage

Commandes de base : `./justice.sh doctor`, `./justice.sh status`, `docker logs --tail 100 <conteneur>`, et l'onglet **Journaux** de la Console.

## Démarrage et Docker

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ERREUR: configure X dans config/config.env` | Secret absent ou `CHANGE_ME` | Générer : `openssl rand -hex 32`, renseigner, relancer `check` |
| `Cannot connect to the Docker daemon` | Docker arrêté | Lancer Docker Desktop / OrbStack / Colima, ou `sudo systemctl start docker` |
| `permission denied … docker.sock` (Linux) | Utilisateur hors du groupe `docker` | `sudo usermod -aG docker $USER` puis se reconnecter |
| `docker: 'compose' is not a docker command` | Plugin Compose v2 absent | Installer `docker-compose-plugin` ; Docker Desktop l'inclut |
| `port is already allocated` (5678, 8443, 8801, 8830) | Port pris par un autre programme | `lsof -i :8801` ; arrêter le programme concerné ou modifier le mapping de ports dans `docker-compose.yml` |
| Un service reste `unhealthy` / `starting` | Dépendance pas prête (ex. `martian-db`) | Attendre ~1–2 min ; sinon lire les journaux du service et de `martian-db` |
| `no space left on device` | Disque Docker plein | `docker system df` ; `docker image prune` ; `docker builder prune` |
| Mot de passe PostgreSQL « authentication failed » après modification de `config.env` | Le mot de passe est figé dans le volume à l'initialisation | `ALTER USER martian PASSWORD '…'` (ou `justice`) dans la base, ou recréer le volume (perte de données) |

## Console

| Symptôme | Solution |
|---|---|
| Demande de mot de passe en boucle | Vérifier `SOC_ADMIN_USER`/`SOC_ADMIN_PASSWORD` dans `config.env` ; recréer le conteneur après changement (`./justice.sh deploy`) |
| `Trop d'échecs, réessayez dans 2 minutes` (429) | Blocage anti-bruteforce par IP : attendre 2 min |
| `Configure SOC_ADMIN_PASSWORD` (503) | Variable vide : renseigner et redéployer |
| `Docker indisponible` | Le socket n'est pas monté/accessible. Colima : exporter `DOCKER_HOST` ou lier `/var/run/docker.sock` |
| `Requête refusée (CSRF)` (403) | Appel API manuel sans en-tête `X-JLC: 1` |
| Outils : « Conteneur … introuvable : déployez la stack » | Le conteneur de l'outil n'existe pas (stack non déployée) |
| Outils : « Le conteneur … n'est pas démarré » | Démarrez-le depuis l'onglet Conteneurs |
| Outils : « Cette action est déjà en cours » | Une même action ne peut tourner qu'une fois à la fois ; attendre la fin |
| Liste de sous-réseaux vide pour la découverte | `AUTHORIZED_CIDRS` est vide : le renseigner (séparés par des espaces) et redéployer `green-arrow` |
| Liste des fichiers vide | Rien n'a encore été généré ; lancer une action, ou changer de dossier avec le sélecteur |

## Scanner de ports (GREEN ARROW)

| Symptôme | Cause / solution |
|---|---|
| `ERREUR: … hors de AUTHORIZED_CIDRS` | Cible hors périmètre : intentionnel. Ajouter le réseau **seulement s'il est autorisé** |
| Découverte ARP : 0 équipement | Conteneur sur un bridge/VM : ARP ne traverse pas. Utiliser les scripts natifs (macOS/Windows) ou `network_mode: host` (Linux) |
| `PermissionError` / ARP refusé | `NET_RAW` manquant (déjà ajouté dans le compose) ; en natif : `sudo` / administrateur |
| « Aucun port correspondant détecté » (audit local) | Le conteneur n'a aucun port en écoute : normal ; il décrit le conteneur, pas l'hôte |
| Scan complet très long | 65 535 ports × 200 threads par hôte ; limité à 60 min par la Console |

## OSINT et veille

| Symptôme | Solution |
|---|---|
| « Aucun domaine. Ajoute-en… » | Renseigner `OSINT_DOMAINS` ou utiliser l'action **Ajouter un domaine** |
| `crt.sh KO … repli certspotter` | crt.sh est souvent lent/indisponible : le repli est automatique ; réessayer plus tard |
| Résultats DNS vides | DoH bloqué par le pare-feu sortant (Cloudflare/Google) |
| WATCHTOWER `feeds_errors` non vide | Flux indisponible ou URL changée : corriger `config/watchtower/feeds.json` |
| NVD lent / 403 / 429 | Renseigner `NVD_API_KEY` ; augmenter `WATCH_NVD_INTERVAL` |
| `veille_cyber.py` : « téléchargement impossible » | Sortie HTTPS bloquée (proxy/pare-feu) ; vérifier depuis le conteneur : `docker exec justice-league-watchtower python -c "import urllib.request;print(urllib.request.urlopen('https://www.cert.ssi.gouv.fr/feed/').status)"` |
| Les alertes ne partent pas | `NOTIFY_DRY_RUN=YES` (défaut) ou webhook vide ; vérifier `GET green-lantern:8898/health` |

## SOC, MARTIAN, IA

| Symptôme | Solution |
|---|---|
| `AI unavailable` / `AI interpretation unavailable` | Modèle non téléchargé ou Ollama injoignable : `docker exec martian-ollama ollama pull <modèle>` ; vérifier `OLLAMA_URL` |
| Réponses IA très lentes | Normal sur CPU. Mac : Ollama natif (GPU). Modèle plus petit/quantifié |
| Collecteurs sans événements | Les fichiers sont-ils dans `LOG_ROOT` (`suricata/eve.json`, `zeek/conn.log.json`, `wazuh/alerts.json`) ? Format JSON lignes ? Lire `docker logs justice-league-collectors` |
| `./justice.sh verify` : `:8787` non disponible | Normal : MARTIAN n'est pas publié sur l'hôte |
| Page SOC : avertissement de certificat | Normal (`tls internal`) ; accepter l'exception ou importer la CA de Caddy |

## macOS / Apple Silicon

| Symptôme | Solution |
|---|---|
| Construction lente / mémoire insuffisante | Docker Desktop > Settings > Resources : ≥ 6–8 Go de RAM |
| Bind mount refusé / `mounts denied` | Le dossier doit être dans un chemin partagé avec Docker (`/Users/…`). Utilisez le projet dans votre dossier personnel |
| `exec format error` | Image/binaire d'une autre architecture : ne forcez pas `platform: linux/amd64` ; reconstruisez (`--build`) |
| `host.docker.internal` injoignable depuis Ollama natif | Lancer `ollama serve` ; `OLLAMA_URL=http://host.docker.internal:11434` ; `./justice.sh doctor` teste la liaison |
| `[bug-bounty] paquet X indisponible sur arm64` | Attendu : outil APT optionnel absent pour ARM64, ignoré. Compilez-le via Go/pip si nécessaire |
| Échec `go install …@latest` pendant le build du lab | Réseau/limite GitHub : relancer `--build` ; épingler une version (`@vX.Y.Z`) dans le Dockerfile |
| Découverte ARP vide | Limite connue de Docker Desktop (voir ci-dessus) : scripts natifs avec `sudo` |

## Réinitialisation

```bash
# Redémarrer proprement un service
docker restart <conteneur>

# Repartir de zéro (SUPPRIME toutes les données : bases, rapports, modèles)
./justice.sh stop
docker compose --env-file config/config.env -f docker/docker-compose.yml --profile ollama down -v
./justice.sh deploy
```

## Collecter des informations pour un signalement

```bash
./justice.sh doctor
./justice.sh status
docker logs --tail 200 <conteneur_en_erreur>
docker version --format '{{.Server.Version}} {{.Server.Arch}}'
```
Ne joignez **jamais** `config.env` ni de jetons/mots de passe.
