# Justice League Homelab — V9 FINAL+ Bug Bounty

V9 extends the SOC with a dedicated Bug Bounty/AppSec environment.

```text
JUSTICE LEAGUE HQ
       |
       +-- SOC Command Center
       +-- MARTIAN-MANHUNTER
       +-- BATMAN / n8n
       +-- CYBORG / Wazuh + Suricata
       +-- FLASH / Zeek
       +-- ORACLE / CTI
       +-- SUPERMAN / Assets
       |
       +-- BUG BOUNTY LAB (isolated container)
              |-- Recon
              |-- DNS/HTTP
              |-- Crawling
              |-- Fuzzing
              |-- Nuclei
              |-- Web assessment
              |-- Source/AppSec
              `-- SecLists
```

The Bug Bounty Lab is restricted by an explicit scope file and is intended only for authorized programs/assets.

## V9 Bug Bounty workflow

Use `./scripts/bug-bounty-pipeline.sh authorized.example passive` for passive reconnaissance, or `active` only when the program explicitly permits active testing. See `docker/bug-bounty/README-BUG-BOUNTY.md` and `templates/BUG-REPORT.md`.
