#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
test -f config/config.env || { echo "Missing config/config.env; run bootstrap-v7.sh"; exit 1; }
set -a; source config/config.env; set +a
cd docker
docker compose -f compose.yml -f compose.v6.yml -f compose.v7.yml up -d --build
echo "[V7] Justice League SOC deployed."
echo "[V7] Command Center: http://127.0.0.1:8800"
