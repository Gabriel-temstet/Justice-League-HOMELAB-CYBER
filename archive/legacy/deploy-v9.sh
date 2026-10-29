#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p config/bug-bounty
[[ -f config/bug-bounty/targets.json ]] || cp config/bug-bounty/targets.example.json config/bug-bounty/targets.json
if ! docker network inspect justice >/dev/null 2>&1; then docker network create justice >/dev/null; fi
docker compose -f docker/compose.yml -f docker/compose.v6.yml -f docker/compose.v7.yml -f docker/compose.v8.yml -f docker/compose.v9.yml up -d --build bug-bounty-lab
echo 'Bug Bounty container deployed.'
echo 'Configure config/bug-bounty/targets.json before running scans.'
