#!/usr/bin/env bash
set -euo pipefail
M="${MARTIAN_URL:-http://127.0.0.1:8787}"
B="${BATMAN_URL:-http://127.0.0.1:8790}"
G="${GREEN_LANTERN_URL:-http://127.0.0.1:8899}"
curl -fsS "$M/health" >/dev/null
curl -fsS "$B/health" >/dev/null
curl -fsS "$G/health" >/dev/null
curl -fsS -X POST "$B/normalize?source=smoke-test&forward=true" -H 'Content-Type: application/json'   -d '{"event_type":"network_alert","severity":"high","src_ip":"10.10.30.21","dst_ip":"10.10.30.50","signature":"smoke"}' >/dev/null
echo "V6 smoke test OK"
