#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo 'Usage: sudo ./scripts/restore-v8.sh /path/backup.tgz'; exit 1; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
 tar -xzf "$1" -C "$tmp"; d=$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -1)
cd "$ROOT"; set -a; source config/config.env; set +a
docker compose --env-file config/config.env -f docker/compose.v8.yml up -d martian-db batman-postgres
sleep 5
docker exec -i martian-db psql -U martian -d martian < "$d/martian.sql"
docker exec -i batman-postgres psql -U justice -d justice < "$d/batman.sql"
echo 'Restore complete. Review config/config.env and run verify-v8.sh.'
