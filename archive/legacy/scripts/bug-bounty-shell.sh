#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker exec -it justice-league-bug-bounty bash
