# Installation V8 FINAL

## 1. Prérequis

Linux Debian/Ubuntu recommandé, une machine allumée en permanence, Docker/Compose (installés automatiquement si absents sur Debian/Ubuntu), et suffisamment de RAM/CPU pour Ollama + SIEM.

Pour une cible confortable : 16 cœurs, 128 Go RAM, 2 To NVMe + stockage secondaire, NIC 2.5/10 GbE.

## 2. Installation

```bash
sudo ./scripts/install-v8.sh
./scripts/verify-v8.sh
```

L'installateur :

1. installe Docker si nécessaire ;
2. génère les secrets ;
3. crée les répertoires de logs ;
4. build et démarre les services ;
5. attend le healthcheck du SOC ;
6. active le démarrage systemd.

## 3. Accès

- SOC : `https://127.0.0.1:8443`
- n8n : `http://127.0.0.1:5678`
- MARTIAN : réseau Docker uniquement

Le certificat du SOC est généré par Caddy en autorité locale. Le navigateur peut demander de faire confiance à l'autorité locale Caddy.

## 4. Ingestion

Déposer des JSON Lines dans :

- `/srv/justice-league/logs/suricata/eve.json`
- `/srv/justice-league/logs/zeek/conn.log.json`
- `/srv/justice-league/logs/wazuh/alerts.json`

Le collecteur normalise automatiquement vers MARTIAN.

## 5. CTI

ORACLE surveille les flux RSS configurés dans `CTI_FEEDS` et persiste les nouveaux articles comme entités CTI dans MARTIAN.

## 6. Asset discovery

GREEN ARROW est volontairement désactivé par défaut. Pour scanner uniquement un périmètre autorisé :

```dotenv
AUTHORIZED_CIDRS=192.168.1.0/24 10.10.20.0/24
```

Puis :

```bash
docker compose --env-file config/config.env -f docker/compose.v8.yml up -d --build green-arrow
```

## 7. Notifications

Discord : `DISCORD_WEBHOOK_URL`.

WhatsApp : `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TO`.

Puis `NOTIFY_DRY_RUN=NO` et `docker compose ... up -d --build green-lantern`.

## 8. Sauvegarde / restauration

```bash
sudo ./scripts/backup-v8.sh
sudo ./scripts/restore-v8.sh /srv/justice-league-backups/v8-YYYYMMDD-HHMMSS.tgz
```

## 9. Démo contrôlée

```bash
./scripts/seed-v8.sh
```

Cela injecte un événement synthétique dans MARTIAN afin de valider la chaîne sans toucher au réseau réel.
