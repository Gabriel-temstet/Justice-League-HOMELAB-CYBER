# Justice League V8 — FINAL architecture

```text
                         HOME / LAB NETWORK
                                |
                       SPAN / TAP / SENSOR
                                |
                 +--------------+--------------+
                 |                             |
              FLASH                         CYBORG
           Zeek JSON                    Wazuh / Suricata
                 |                             |
                 +-------------+---------------+
                               |
                         BATMAN / n8n
                               |
                        NORMALIZATION
                               |
                      MARTIAN-MANHUNTER
                     PostgreSQL + Ollama
                               |
          +--------------------+--------------------+
          |                    |                    |
      SUPERMAN               ORACLE             HISTORY
      assets/CVE               CTI              timeline
          |                    |                    |
          +--------------------+--------------------+
                               |
                    SOC COMMAND CENTER V8
              Auth / Cases / Audit / Search / Graph
                               |
                       GREEN LANTERN
                  Discord / WhatsApp adapters
                               |
                         HUMAN APPROVAL
```

## Security model

Read → normalize → correlate → explain → propose. Disruptive remediation is never automatic. The dashboard is authenticated, local-only by default, and exposed through Caddy with an internal TLS certificate.
