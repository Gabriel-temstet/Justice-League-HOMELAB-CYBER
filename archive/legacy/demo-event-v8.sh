#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"; set -a; source config/config.env; set +a
curl -fsS -X POST http://127.0.0.1:8790/normalize -H 'Content-Type: application/json' -H "X-AI-Gateway-Token: $AI_GATEWAY_TOKEN" -d '{"source":"demo","event_type":"authentication_failure","severity":"high","data":{"src_ip":"192.0.2.10","hostname":"demo-host","message":"repeated authentication failures"}}' || true
echo 'If the legacy normalizer route is unavailable, use scripts/seed-v8.py.'
