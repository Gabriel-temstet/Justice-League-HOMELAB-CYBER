# V8 FINAL status

## Included and wired

- MARTIAN persistent memory in PostgreSQL
- BATMAN/n8n orchestration service
- event normalization and persistence
- high/critical → investigation + GREEN LANTERN notification path
- Suricata/Zeek/Wazuh JSON tail collector
- authenticated SOC Command Center
- cases, notes, event attachment and audit log
- relationship graph API
- local evidence-first MARTIAN Q&A using Ollama
- Discord and WhatsApp Cloud API notification adapters
- Caddy internal TLS endpoint
- systemd autostart
- backup/restore and verification scripts
- generated secrets during installation

## Deliberately external

Software cannot automatically create or physically configure:

- switch SPAN/TAP;
- physical NIC topology;
- remote Wazuh/Zeek/Suricata sensors;
- Discord/Meta accounts and credentials;
- Proxmox host/VM hardware configuration.

Those are explicit environment inputs. The software stack is otherwise designed to start and self-check from a single Linux machine.
