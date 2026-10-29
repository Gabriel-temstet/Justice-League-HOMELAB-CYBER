#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-}"
MODE="${2:-passive}"
PROFILE="${3:-authorized}"
[[ -n "$TARGET" ]] || { echo "Usage: $0 target [passive|active] [authorized|lab]"; exit 2; }
cd "$ROOT"
docker compose -f docker/compose.yml -f docker/compose.v6.yml -f docker/compose.v7.yml -f docker/compose.v8.yml -f docker/compose.v9.yml run --rm bug-bounty-lab /bin/bash -lc "bb-pipeline.sh '$TARGET' '$MODE' '$PROFILE'"
