#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ $EUID -ne 0 ]]; then echo 'Run as root: sudo ./scripts/install-v8.sh'; exit 1; fi
if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl openssl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$(. /etc/os-release; echo \"$ID\") $(. /etc/os-release; echo \"$VERSION_CODENAME\") stable" >/etc/apt/sources.list.d/docker.list
    apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
  else echo 'Docker absent and automatic installation is supported only on Debian/Ubuntu-like systems.'; exit 2; fi
fi
command -v openssl >/dev/null || apt-get install -y openssl
mkdir -p config "$ROOT/runtime/logs" /srv/justice-league/logs /srv/justice-league-backups
chmod 700 config
if [[ ! -f config/config.env ]]; then cp config/config.env.example config/config.env; fi
set -a; source config/config.env; set +a
rand(){ openssl rand -hex 24; }
replace(){ local k="$1"; local v="$2"; sed -i -E "s#^${k}=.*#${k}=${v}#" config/config.env; }
[[ "$MARTIAN_DB_PASSWORD" == CHANGE_ME ]] && replace MARTIAN_DB_PASSWORD "$(rand)"
[[ "$BATMAN_DB_PASSWORD" == CHANGE_ME ]] && replace BATMAN_DB_PASSWORD "$(rand)"
[[ "$AI_GATEWAY_TOKEN" == CHANGE_ME ]] && replace AI_GATEWAY_TOKEN "$(rand)"
[[ "$N8N_ENCRYPTION_KEY" == CHANGE_ME ]] && replace N8N_ENCRYPTION_KEY "$(rand)$(rand | cut -c1-16)"
[[ "$SOC_ADMIN_PASSWORD" == CHANGE_ME ]] && replace SOC_ADMIN_PASSWORD "$(rand)"
set -a; source config/config.env; set +a
for req in MARTIAN_DB_PASSWORD BATMAN_DB_PASSWORD AI_GATEWAY_TOKEN N8N_ENCRYPTION_KEY SOC_ADMIN_PASSWORD; do [[ -n "${!req:-}" ]] || { echo "Missing $req in config/config.env"; exit 4; }; done
chmod 600 config/config.env
set -a; source config/config.env; set +a
mkdir -p /srv/justice-league/logs/{suricata,zeek,wazuh}
docker compose --env-file config/config.env -f docker/compose.v8.yml build
docker compose --env-file config/config.env -f docker/compose.v8.yml up -d
for i in {1..60}; do if curl -ksf https://127.0.0.1:8443/health >/dev/null 2>&1; then break; fi; sleep 2; done
if ! curl -ksf https://127.0.0.1:8443/health >/dev/null; then docker compose --env-file config/config.env -f docker/compose.v8.yml ps; exit 3; fi
cat > /etc/systemd/system/justice-league-v8.service <<EOF
[Unit]
Description=Justice League SOC V8
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
WorkingDirectory=$ROOT
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose --env-file $ROOT/config/config.env -f $ROOT/docker/compose.v8.yml up -d
ExecStop=/usr/bin/docker compose --env-file $ROOT/config/config.env -f $ROOT/docker/compose.v8.yml down
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl enable justice-league-v8.service >/dev/null
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
printf 'Justice League V8 installed.\n'
printf 'SOC: https://127.0.0.1:8443  (self-signed/internal CA)\n'
printf 'LAN: bind is localhost by default; change port mapping if you deliberately expose it.\n'
printf 'User: %s\nPassword: stored in config/config.env\n' "$SOC_ADMIN_USER"
printf 'n8n: http://127.0.0.1:5678\n'
printf 'Logs: /srv/justice-league/logs/{suricata,zeek,wazuh}\n'
