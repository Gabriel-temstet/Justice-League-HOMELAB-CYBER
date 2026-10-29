# JUSTICE LEAGUE HOMELAB V7 — SOC COMMAND CENTER

## Runtime

```text
                    HOME / LAB NETWORK
                           |
                 SPAN / TAP (physical)
                           |
              +------------+------------+
              |                         |
          FLASH                       CYBORG
       Zeek/Suricata                  Wazuh
              \                         /
               +-------- BATMAN --------+
                        n8n
                         |
                   normalization
                         |
                 MARTIAN-MANHUNTER
               PostgreSQL memory
                         |
        +----------------+----------------+
        |                |                |
    SUPERMAN          ORACLE          HISTORY
    Assets/CVE          CTI           Timeline
        +----------------+----------------+
                         |
                 SOC COMMAND CENTER
                         |
              GREEN LANTERN alerts
                         |
                   Human approval
```

## V7 adds

- Web SOC Command Center on port 8800 (localhost by default)
- operational health checks
- first-run bootstrap
- deterministic verification
- backups
- persistent event/investigation views
- n8n intake workflow
- explicit dry-run notification mode
- one-command deployment after configuration

## Physical requirement

Network visibility still requires a managed switch/router capable of SPAN/port mirroring
or an equivalent TAP. Software cannot manufacture packets that never reach the sensor.
