#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-$(pwd)/backups}"; mkdir -p "$OUT"
docker exec martian-db pg_dump -U martian -d martian > "$OUT/martian-$(date +%Y%m%d-%H%M%S).sql"
echo "MARTIAN backup created in $OUT"
