#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/backups}"; mkdir -p "$OUT"
STAMP="$(date +%Y%m%d-%H%M%S)"
docker exec martian-db pg_dump -U martian -d martian > "$OUT/martian-$STAMP.sql"
tar -czf "$OUT/config-$STAMP.tgz" -C "$ROOT" config
echo "Backup created: $OUT/*-$STAMP.*"
