# Installation V7

## 1. Prepare host

Recommended: Debian/Ubuntu server or the Proxmox control-plane described by the project.
Docker Engine + Compose are required for the control plane.

## 2. Bootstrap

```bash
chmod +x scripts/*.sh
./scripts/bootstrap-v7.sh
nano config/config.env
```

Set at minimum:
- MARTIAN_DB_PASSWORD
- AI_GATEWAY_TOKEN

For real Discord alerts:
- DISCORD_WEBHOOK_URL
- NOTIFY_DRY_RUN=NO

## 3. Deploy

```bash
./scripts/deploy-v7.sh
./scripts/verify-v7.sh
```

## 4. Command Center

Open:

`http://127.0.0.1:8800`

It displays:
- 24h event count
- high/critical count
- open investigations
- asset count
- indicator count
- event stream
- investigations
- service health
- search

## 5. Network telemetry

Connect a SPAN/TAP source to FLASH/Suricata/Zeek according to the topology.
The V7 software stack does not pretend that a physical mirror port can be configured
from inside the host.

## 6. External providers

Discord can be enabled with a webhook.

WhatsApp requires an actual provider/account/token. The project deliberately does not
embed fake credentials or pretend that WhatsApp is connected when it is not.
