# Justice League Homelab — V8 FINAL

V8 is the final production-oriented one-machine SOC stack. It keeps the Justice League roles and closes the main V7 gaps:

- one Compose deployment for the core stack;
- automatic Docker installation on Debian/Ubuntu-like hosts;
- generated secrets and persistent PostgreSQL memory;
- authenticated SOC Command Center;
- incident/case management, notes, audit log and relationship graph API;
- MARTIAN evidence-first question/answer with local Ollama;
- native JSON tail ingestion for Suricata EVE, Zeek JSON and Wazuh alert JSON;
- GREEN LANTERN Discord + WhatsApp Cloud API adapters;
- n8n/BATMAN orchestration kept available;
- Caddy local TLS endpoint;
- systemd autostart;
- backup and restore of both PostgreSQL databases + configuration;
- health verification.

## Install

```bash
sudo ./scripts/install-v8.sh
./scripts/verify-v8.sh
```

SOC: `https://127.0.0.1:8443`

The generated administrator password is in `config/config.env`.

## Real network feeds

Mount or write these files on the host:

- `/srv/justice-league/logs/suricata/eve.json`
- `/srv/justice-league/logs/zeek/conn.log.json`
- `/srv/justice-league/logs/wazuh/alerts.json`

The collector tails JSON lines and normalizes them into MARTIAN memory.

## Notifications

Discord: set `DISCORD_WEBHOOK_URL` and change `NOTIFY_DRY_RUN=NO`.

WhatsApp: set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TO` and `NOTIFY_DRY_RUN=NO`. This requires an authorized Meta WhatsApp Cloud API sender; the software cannot create the external account for you.

## Physical prerequisites that no software can invent

- managed switch/SPAN or TAP for passive network visibility;
- appropriate NIC(s), ideally 2.5/10 GbE for sustained monitoring;
- Wazuh/Zeek/Suricata agents or sensors producing the configured JSON logs;
- external Discord/WhatsApp credentials if notifications are desired;
- Proxmox and VM provisioning remain environment-specific.

V8 therefore means **turnkey software deployment**, not fabricated access to physical network hardware or third-party accounts.
