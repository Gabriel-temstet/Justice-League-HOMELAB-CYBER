#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p backups data logs
if [ ! -f config/config.env ]; then
  cp config/config.env.example config/config.env
  chmod 600 config/config.env
  echo "[V7] config/config.env created. Review secrets before production use."
fi
set -a
source config/config.env
set +a

if command -v openssl >/dev/null 2>&1; then
  if grep -q '^MARTIAN_DB_PASSWORD=CHANGE_ME' config/config.env; then
    sed -i "s/^MARTIAN_DB_PASSWORD=.*/MARTIAN_DB_PASSWORD=$(openssl rand -hex 24)/" config/config.env
  fi
  if grep -q '^AI_GATEWAY_TOKEN=CHANGE_ME' config/config.env; then
    sed -i "s/^AI_GATEWAY_TOKEN=.*/AI_GATEWAY_TOKEN=$(openssl rand -hex 32)/" config/config.env
  fi
fi
echo "[V7] configuration initialized."
echo "[V7] Run scripts/deploy-v7.sh then scripts/verify-v7.sh"
