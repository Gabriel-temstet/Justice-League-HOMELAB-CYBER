#!/usr/bin/env bash
set -euo pipefail
ROOT="${DATA_ROOT:-/srv/justice-league}"
for d in "$ROOT"/batman "$ROOT"/oracle "$ROOT"/martian "$ROOT"/green-lantern "$ROOT"/monitoring; do
  [[ -f "$d/docker-compose.yml" ]] && (cd "$d" && docker compose pull && docker compose up -d)
done
echo "Justice League control plane updated."
