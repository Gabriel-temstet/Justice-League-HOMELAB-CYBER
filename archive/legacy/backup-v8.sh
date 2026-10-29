#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
set -a; source config/config.env; set +a
mkdir -p "$BACKUP_ROOT"
ts=$(date +%Y%m%d-%H%M%S); out="$BACKUP_ROOT/v8-$ts"; mkdir -p "$out"
docker exec martian-db pg_dump -U martian -d martian > "$out/martian.sql"
docker exec batman-postgres pg_dump -U justice -d justice > "$out/batman.sql"
cp config/config.env "$out/config.env"
tar -C "$BACKUP_ROOT" -czf "$BACKUP_ROOT/v8-$ts.tgz" "v8-$ts"
rm -rf "$out"
echo "$BACKUP_ROOT/v8-$ts.tgz"
