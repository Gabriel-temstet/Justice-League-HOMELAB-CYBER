#!/usr/bin/env bash
# Déploie (ou met à jour) le conteneur WATCHTOWER sans toucher au reste du SOC.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[[ -f config/config.env ]] || { echo 'config/config.env introuvable : lance d abord install-v8.sh'; exit 1; }
mkdir -p config/watchtower
[[ -f config/watchtower/feeds.json ]] || cp config/watchtower/feeds.example.json config/watchtower/feeds.json
# Détecte le réseau Docker "justice" créé par la V8 (ex. docker_justice)
NET="$(docker network ls --format '{{.Name}}' | grep -E '(^|_)justice$' | head -1 || true)"
if [[ -z "$NET" ]]; then docker network create justice >/dev/null; NET=justice; fi
export JUSTICE_NETWORK="$NET"
# Ajoute les variables WATCH_* à config.env si elles n'y sont pas encore
if ! grep -q '^WATCH_INTERVAL=' config/config.env; then
  { echo; sed -n '/^# --- WATCHTOWER/,$p' config/config.env.example; } >> config/config.env
  echo 'Variables WATCHTOWER ajoutées à config/config.env'
fi
docker compose --env-file config/config.env -f docker/compose.v11.yml up -d --build watchtower
echo "WATCHTOWER déployé sur le réseau '$NET' : http://127.0.0.1:8830"
echo 'Logs : docker logs -f justice-league-watchtower'
