#!/usr/bin/env bash
set -euo pipefail
DEST="${1:-/srv/justice-league/wazuh}"
mkdir -p "$DEST"
cd "$DEST"
if [[ ! -d wazuh-docker ]]; then
  git clone https://github.com/wazuh/wazuh-docker.git -b v4.14.8
fi
cd wazuh-docker/single-node
echo 262144 >/proc/sys/vm/max_map_count
docker compose up -d
echo "Wazuh 4.14.8 single-node deployed."
