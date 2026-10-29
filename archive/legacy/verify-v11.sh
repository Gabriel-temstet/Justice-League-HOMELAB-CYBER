#!/usr/bin/env bash
set -euo pipefail
state=$(docker inspect -f '{{.State.Status}}' justice-league-watchtower 2>/dev/null || echo missing)
health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' justice-league-watchtower 2>/dev/null || echo missing)
printf 'justice-league-watchtower  état=%s  health=%s\n' "$state" "$health"
curl -sf http://127.0.0.1:8830/health | python3 -m json.tool
[[ "$state" == running ]] && echo 'V11 VERIFY: PASS' || { echo 'V11 VERIFY: FAIL'; exit 1; }
