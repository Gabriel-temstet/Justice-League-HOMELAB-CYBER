> **Note** : ce document décrit l'**architecture réseau cible** (sondes, Wazuh, VLAN). Le déploiement logiciel actuel (Docker Compose, version Z) est décrit dans [`docs/03-architecture.md`](docs/03-architecture.md).

# Justice League HQ V3 — Architecture

```text
                         INTERNET
                            |
                    +-------+-------+
                    |  AQUAMAN      |
                    | network edge  |
                    +-------+-------+
                            |
                +-----------+-----------+
                |                       |
             SPAN/TAP                 VLANs
                |                       |
          +-----v------+       +--------v---------+
          |   FLASH    |       | JUSTICE LEAGUE   |
          | Zeek/IDS   |       | service network  |
          +-----+------+       +--------+---------+
                |                       |
                +-----------+-----------+
                            |
                     +------v------+
                     |   CYBORG    |
                     |    Wazuh    |
                     +------+------+
                            |
                     +------v------+
                     |   BATMAN    |
                     |     n8n     |
                     +------+------+
                            |
              +-------------+-------------+
              |                           |
       +------v-------+             +-----v------+
       | MARTIAN CORE |             |   ORACLE   |
       | Ollama / AI  |             | CTI / CVE  |
       +------+-------+             +-----+------+
              |                           |
              +-------------+-------------+
                            |
                    +-------v--------+
                    | WONDER WOMAN  |
                    | reports       |
                    +-------+-------+
                            |
                    +-------v--------+
                    | GREEN LANTERN  |
                    | notifications  |
                    +---+---------+---+
                        |         |
                     Discord   WhatsApp

CYBORG-LAB stays on LAB VLAN and is never bridged directly into management.
```
