#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../docker"
docker compose -f compose.yml -f compose.v6.yml up -d --build
