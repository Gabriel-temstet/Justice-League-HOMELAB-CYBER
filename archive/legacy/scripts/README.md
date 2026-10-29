# Operational scripts

- `healthcheck.sh` — local health overview
- `backup.sh` — tar backup with 14-day local retention
- `update.sh` — update control-plane images
- `install-wazuh.sh` — deploy official Wazuh 4.14.8 single-node stack

For production use, move backups off-host and schedule with systemd timers.
