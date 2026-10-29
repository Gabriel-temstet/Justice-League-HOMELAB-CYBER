# 8. Sécurité

## Cadre légal

Les outils d'audit et de reconnaissance (GREEN ARROW, Bug Bounty Lab, OSINT) ne doivent être employés que :

- sur des systèmes **qui vous appartiennent** ou votre propre laboratoire ;
- ou avec une **autorisation écrite** du propriétaire (périmètre, dates, méthodes) ;
- en respectant les règles des programmes de bug bounty.

En France, l'accès ou le maintien frauduleux dans un système de traitement automatisé de données est puni par les articles 323-1 et suivants du Code pénal ; d'autres pays ont des règles équivalentes. Les garde-fous techniques (`AUTHORIZED_CIDRS`, `scope-guard`) réduisent les erreurs mais **ne remplacent pas l'autorisation**. Le scanner de ports est sous licence « éducation et usage autorisé uniquement » (aucun usage commercial ni redistribution sans accord écrit).

## Principes de conception

| Principe | Mise en œuvre |
|---|---|
| L'IA propose, l'humain décide | `human_approval_required` dès `high` ; aucune remédiation automatique ; l'IA répond uniquement à partir des preuves fournies |
| Moindre exposition | Tous les ports publiés sont liés à `127.0.0.1` ; aucun service n'est destiné à Internet |
| Moindre privilège | Conteneurs durcis (lecture seule, `cap_drop: ALL`, `no-new-privileges`, utilisateur non-root pour WATCHTOWER) ; seul GREEN ARROW reçoit `NET_RAW` |
| Pas de secrets par défaut | `justice.sh check` refuse `CHANGE_ME` et les valeurs vides |
| Liste blanche | La Console n'exécute que des commandes prédéfinies à paramètres validés |
| Traçabilité | Journaux d'audit Console et SOC ; `command-audit.log` du Bug Bounty Lab |

## Surfaces sensibles

| Élément | Risque | Mesure |
|---|---|---|
| `/var/run/docker.sock` monté dans la Console | Contrôle total de l'hôte si la Console est compromise | Port local uniquement, mot de passe fort, blocage anti-bruteforce, CSRF, CSP. Si vous n'en avez pas l'usage : retirer le service `container-manager` du compose |
| `AI_GATEWAY_TOKEN` | Accès aux API internes | Valeur aléatoire longue ; jamais dans un dépôt ; rotation en cas de fuite |
| `config/config.env` | Contient tous les secrets | `chmod 600`, hors dépôt (`.gitignore`), sauvegarde chiffrée |
| n8n | Exécute des workflows, stocke des identifiants | Local uniquement ; conserver `N8N_ENCRYPTION_KEY` ; `N8N_SECURE_COOKIE=false` (HTTP local) : à passer à `true` derrière HTTPS |
| Cookie de session du SOC | `secure=False` (HTTP interne derrière Caddy) | Accès via `https://127.0.0.1:8443` ; durcissable en `secure=True` |
| Caddy `tls internal` | Certificat auto-signé | Avertissement navigateur normal en local ; importez la CA Caddy si besoin |
| Bug Bounty Lab | Outils offensifs | Périmètre `targets.json` strict ; ne pas monter de secrets ; mode passif par défaut |
| Webhooks Discord / jetons WhatsApp | Divulgation via journaux/notifications | Les valeurs sont masquées dans la Console ; ne pas les coller dans les tickets |

## Bonnes pratiques recommandées

1. **Accès distant** : VPN (WireGuard, Tailscale) ou tunnel SSH ; jamais de redirection de port publique.
2. **Mots de passe** : uniques, ≥ 20 caractères (`openssl rand -base64 24`), stockés dans un gestionnaire.
3. **Sauvegardes** : régulières, chiffrées, testées, copie hors site.
4. **Mises à jour** : reconstruire les images régulièrement (`--build`, `pull`) pour recevoir les correctifs ; épingler les versions en production.
5. **Pare-feu hôte** : n'autorisez pas l'entrée sur 8801, 8443, 8830, 5678.
6. **Surveillance de la Console** : `grep AUDIT` périodique sur ses journaux.
7. **Notifications** : passer `NOTIFY_DRY_RUN=NO` seulement après avoir validé le contenu des messages.
8. **Scans** : documentez chaque scan (cible, date, autorisation) ; évitez `SCAN_FULL_PORTS=YES` en continu.
9. **Données personnelles** : les rapports OSINT/veille et les journaux de sondes peuvent en contenir ; appliquez vos règles de rétention (RGPD).
10. **Signalement** : une vulnérabilité de ce projet doit être signalée en privé à son mainteneur avant toute publication.

## Liste de contrôle avant mise en service

- [ ] Tous les `CHANGE_ME` remplacés par des secrets aléatoires
- [ ] `config/config.env` en `chmod 600`, absent du dépôt et sauvegardé de façon sûre
- [ ] Aucun port de la stack accessible depuis le réseau (vérifier avec `docker ps` : tout en `127.0.0.1`)
- [ ] `AUTHORIZED_CIDRS` limité aux réseaux autorisés ; `SCAN_FULL_PORTS=NO` sauf besoin
- [ ] `OSINT_DOMAINS` limité aux domaines autorisés
- [ ] `targets.json` du Bug Bounty Lab conforme au programme
- [ ] Sauvegarde testée (restauration sur machine de test)
- [ ] Accès distant uniquement par VPN/SSH
