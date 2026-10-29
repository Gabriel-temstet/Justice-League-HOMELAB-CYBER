#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/srv/justice-league}"
DEST="${2:-/srv/justice-league-backups}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
tar --exclude='*.log' -czf "$DEST/justice-league-$STAMP.tgz" "$ROOT"
find "$DEST" -type f -name '*.tgz' -mtime +14 -delete
echo "Backup: $DEST/justice-league-$STAMP.tgz"
