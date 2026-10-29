#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/docker/docker-compose.yml"
ENV_FILE="$ROOT/config/config.env"
cd "$ROOT"
env_value(){ grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '"'; }
# Conteneur Ollama uniquement si OLLAMA_URL est vide (sinon Ollama natif, ex. Mac Apple Silicon + GPU Metal)
profiles(){ if [[ -z "$(env_value OLLAMA_URL 2>/dev/null || true)" ]]; then echo "--profile ollama"; fi; }
dc(){ docker compose --env-file "$ENV_FILE" -f "$COMPOSE" $(profiles) "$@"; }
prepare_dirs(){
  local lr; lr="$(env_value LOG_ROOT 2>/dev/null || true)"; lr="${lr:-../data/logs}"
  if [[ "$lr" != /* ]]; then lr="$ROOT/docker/$lr"; fi
  mkdir -p "$lr" "$ROOT/config/watchtower" "$ROOT/config/bug-bounty" 2>/dev/null || true
}
usage(){ cat <<'EOF'
Justice League Homelab — Version Z
Usage: ./justice.sh <doctor|check|deploy|status|verify|logs|stop|backup>
  doctor  Diagnostic de la plateforme (Linux, macOS Intel/Apple Silicon) et de Docker
  check   Vérifie les variables et la configuration Compose
  deploy  Construit et démarre toute la stack unifiée
  status  Affiche l'état des services
  verify  Vérifie les endpoints locaux principaux
  logs    Suit les journaux de la stack
  stop    Arrête la stack (sans supprimer les données)
  backup  Exporte la base MARTIAN et les volumes critiques
EOF
}
case "${1:-}" in
 check)
   [[ -f "$ENV_FILE" ]] || { echo "Copie config/config.env.example vers config/config.env puis configure les secrets."; exit 2; }
   for v in MARTIAN_DB_PASSWORD BATMAN_DB_PASSWORD AI_GATEWAY_TOKEN N8N_ENCRYPTION_KEY SOC_ADMIN_PASSWORD; do
     val="$(env_value "$v")"
     if [[ -z "$val" || "$val" == "CHANGE_ME" ]]; then echo "ERREUR: configure $v dans config/config.env"; exit 2; fi
   done
   dc config -q
   echo "Configuration valide."
   ;;
 doctor)
   echo "Système : $(uname -s) $(uname -m)"
   command -v docker >/dev/null || { echo "ERREUR: Docker introuvable. macOS : installez Docker Desktop (Apple Silicon), OrbStack ou Colima."; exit 2; }
   docker compose version >/dev/null 2>&1 || { echo "ERREUR: plugin Docker Compose v2 manquant."; exit 2; }
   docker info >/dev/null 2>&1 || { echo "ERREUR: le démon Docker ne répond pas (lancez Docker Desktop / OrbStack / Colima)."; exit 2; }
   arch="$(docker info --format '{{.Architecture}}')"; os="$(docker info --format '{{.OperatingSystem}}')"
   mem=$(docker info --format '{{.MemTotal}}'); cpus=$(docker info --format '{{.NCPU}}')
   echo "Docker  : $(docker version --format '{{.Server.Version}}') — $os — architecture $arch"
   echo "Ressources Docker : $cpus CPU, $((mem/1024/1024/1024)) Go de RAM"
   case "$arch" in aarch64|arm64) echo "Architecture ARM64 : images multi-arch natives, aucun émulateur requis." ;; x86_64) echo "Architecture amd64." ;; *) echo "Architecture $arch non testée." ;; esac
   if (( mem < 6*1024*1024*1024 )); then echo "ATTENTION: moins de 6 Go alloués à Docker — augmentez la mémoire (Docker Desktop > Settings > Resources) pour la stack complète."; fi
   if [[ "$os" == *"Docker Desktop"* ]]; then echo "Docker Desktop détecté : les conteneurs tournent dans une VM Linux (le scanner réseau ne voit pas le LAN de l'hôte, voir README)."; fi
   if [[ -n "$(env_value OLLAMA_URL 2>/dev/null || true)" ]]; then
     echo "IA : Ollama externe ($(env_value OLLAMA_URL))"; curl -fs --max-time 3 "$(env_value OLLAMA_URL | sed 's#host.docker.internal#127.0.0.1#')/api/tags" >/dev/null && echo "     Ollama natif joignable." || echo "     ATTENTION: Ollama natif injoignable (ollama serve ?)."
   else echo "IA : conteneur Ollama (CPU). Sur Mac, Ollama natif est bien plus rapide (voir config.env)."; fi
   ;;
 deploy)
   "$ROOT/justice.sh" check
   prepare_dirs
   dc up -d --build
   echo "Stack Z démarrée. Gestionnaire: http://127.0.0.1:8801"
   ;;
 status) dc ps ;;
 verify)
   dc ps
   for url in http://127.0.0.1:8801/health http://127.0.0.1:8830/health http://127.0.0.1:8787/health; do
     if curl -fsS --max-time 4 "$url" >/dev/null; then echo "OK  $url"; else echo "NON DISPONIBLE (peut être normal si service arrêté): $url"; fi
   done
   ;;
 logs) dc logs -f --tail=150 ;;
 stop) dc stop ;;
 backup)
   command -v docker >/dev/null
   mkdir -p "${BACKUP_ROOT:-$ROOT/backups}"
   dest="${BACKUP_ROOT:-$ROOT/backups}/justice-z-$(date +%Y%m%d-%H%M%S)"
   mkdir -p "$dest"
   dc exec -T martian-db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$dest/martian.sql"
   dc exec -T batman-postgres sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$dest/batman.sql"
   tar -czf "$dest/config-and-reports.tgz" config/watchtower config/bug-bounty 2>/dev/null || true
   echo "Sauvegarde créée: $dest (copie-la également hors de l'hôte)."
   ;;
 *) usage; exit 2 ;;
esac
