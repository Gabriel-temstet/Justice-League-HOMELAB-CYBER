#!/usr/bin/env bash
set -euo pipefail
echo "=== JUSTICE LEAGUE HQ V3 HEALTH ==="
echo
for u in \
  http://127.0.0.1:8787/health \
  http://127.0.0.1:8899/health \
  http://127.0.0.1:3001; do
  printf "%-40s " "$u"
  if curl -fsS --max-time 4 "$u" >/dev/null 2>&1; then echo "ONLINE"; else echo "OFFLINE"; fi
done
echo
if command -v pvesh >/dev/null 2>&1; then
  echo "--- VMs ---"
  pvesh get /cluster/resources --type vm 2>/dev/null || true
fi
