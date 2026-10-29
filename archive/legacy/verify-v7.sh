#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BASE="${SOC_URL:-http://127.0.0.1:8800}"
curl -fsS "$BASE/health" >/dev/null
curl -fsS "$BASE/api/overview" >/dev/null
curl -fsS "$BASE/api/service-check" >/dev/null
echo "[V7] Command Center OK"
echo "[V7] Overview API OK"
echo "[V7] Internal service checks OK"
