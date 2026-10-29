#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"; set -a; source config/config.env; set +a
curl -fsS -X POST http://127.0.0.1:8787/ingest -H 'Content-Type: application/json' -H "X-AI-Gateway-Token: $AI_GATEWAY_TOKEN" -d '{"source":"demo","event_type":"authentication_failure","severity":"high","external_id":"demo:001","asset_ids":["demo-host"],"indicators":["192.0.2.10"],"data":{"src_ip":"192.0.2.10","hostname":"demo-host","message":"repeated authentication failures"}}'
echo
