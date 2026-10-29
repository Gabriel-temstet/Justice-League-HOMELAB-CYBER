#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
set -a; source config/config.env; set +a
fail=0
for svc in martian-db martian-core batman-postgres batman-n8n batman-normalizer green-lantern collectors soc-command-center caddy; do
  state=$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || echo missing)
  printf '%-28s %s\n' "$svc" "$state"
  [[ "$state" == running ]] || fail=1
done
curl -ksf https://127.0.0.1:8443/health >/dev/null && echo 'SOC health: OK' || { echo 'SOC health: FAIL'; fail=1; }
[[ $fail -eq 0 ]] && echo 'V8 VERIFY: PASS' || { echo 'V8 VERIFY: FAIL'; exit 1; }
