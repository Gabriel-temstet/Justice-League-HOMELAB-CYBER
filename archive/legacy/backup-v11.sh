#!/usr/bin/env bash
# Sauvegarde la base et les rapports de WATCHTOWER (volume docker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/justice-league-backups}"; mkdir -p "$BACKUP_ROOT"
VOL="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' justice-league-watchtower)"
out="$BACKUP_ROOT/watchtower-$(date +%Y%m%d-%H%M%S).tgz"
docker run --rm -v "$VOL":/data:ro -v "$BACKUP_ROOT":/out alpine tar -C /data -czf "/out/$(basename "$out")" .
echo "$out"
