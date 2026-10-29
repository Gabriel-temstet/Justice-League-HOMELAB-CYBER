# 10. Développement

## Structure du dépôt

```
justice-league-homelab-z/
├── justice.sh                      # point d'entrée opérationnel unique
├── README.md  ARCHITECTURE.md      # vue d'ensemble / architecture réseau cible
├── docs/                           # cette documentation
├── config/
│   ├── config.env.example          # modèle de configuration (copier vers config.env)
│   ├── watchtower/feeds.example.json
│   └── bug-bounty/{targets,program}.example.json
├── docker/
│   ├── docker-compose.yml          # stack complète (source de vérité)
│   ├── container-manager/          # Console : app.py, tools.py, static/{index.html,app.js,style.css}
│   ├── martian-core/               # API de mémoire/corrélation (FastAPI + psycopg)
│   ├── v8-api/                     # SOC Command Center (image du service justice-league-soc)
│   ├── batman/                     # normalizer + workflows n8n d'exemple
│   ├── collectors/  notify/        # collecteurs de journaux ; GREEN LANTERN
│   ├── oracle/                     # CTI (app.py) + osint/ + start.sh + tool_cli.py
│   ├── green-arrow/                # scanner.sh + tools/ + run_audits.py + tool_cli.py + start.sh
│   ├── watchtower/                 # app.py (API) + veille-cyber/ + start.sh
│   ├── bug-bounty/                 # Dockerfile, scope-guard.py, bb-run, workflows/, templates/
│   ├── caddy/  ops/                # Caddyfile ; healthcheck.py
│   ├── compose.yml  soc-command-center/   # hérités, non utilisés
│   └── <service>/docker-compose.yml       # hérités par service, non utilisés
├── scripts/                        # (renvoie vers justice.sh)
└── archive/legacy/                 # versions V3–V11, référence uniquement
```

**Règle du projet** : une seule version active. Toute nouvelle fonctionnalité est intégrée à la version Z (`docker/docker-compose.yml`, `justice.sh`, la Console), sans nouvelle série de scripts versionnés.

## Conventions

- Compose : `restart: unless-stopped`, réseau `justice`, ports publiés **uniquement** en `127.0.0.1:`, *healthcheck* pour tout service HTTP, durcissement (`read_only`, `cap_drop: ALL`, `no-new-privileges`) dès que possible.
- Variables : lues avec une valeur par défaut `${VAR:-défaut}` ; documentées dans `config.env.example` **et** dans [Configuration](02-configuration.md).
- Secrets : jamais dans le dépôt, jamais en dur ; refusés s'ils valent `CHANGE_ME` (ajouter la variable à `check` dans `justice.sh`).
- Multi-architecture : pas de binaire pré-compilé ni de `platform:` ; préférer des images/paquets multi-arch ; les paquets optionnels ne doivent pas faire échouer le build.
- Interactions IA : l'IA ne déclenche jamais d'action sensible ; sorties fondées sur des preuves.
- Langue : documentation et interface en français.

## Ajouter un outil à la Console

1. Intégrer l'outil dans l'image du conteneur cible (Dockerfile) et fournir un lanceur **non interactif** (`tool_cli.py`) qui valide ses entrées.
2. Ajouter une entrée dans `TOOLS` de `docker/container-manager/tools.py` (voir [Console](04-console.md#ajouter-un-outil-à-la-console)). Utiliser `timeout`, des paramètres validés et des listes d'arguments.
3. Si l'outil doit démarrer avec le conteneur : un `start.sh` qui lance l'outil en arrière-plan et `exec` le service principal (ou `wait -n`).
4. Documenter ([Outils intégrés](05-outils-integres.md)) et ajouter les variables à `config.env.example`.

## Ajouter un service à la stack

1. Créer `docker/<service>/` (Dockerfile, code, `requirements.txt` épinglé).
2. Déclarer le service dans `docker/docker-compose.yml` (réseau `justice`, *healthcheck*, `depends_on` avec `condition: service_healthy` si pertinent).
3. Ajouter son codename dans `ROLES` de `container-manager/app.py` pour l'affichage.
4. Mettre à jour [Architecture](03-architecture.md), [Référence des API](06-reference-api.md) et la sauvegarde (`justice.sh backup`) s'il persiste des données.

## Développer en local

```bash
# Valider la composition
sed 's/CHANGE_ME/x/' config/config.env.example > /tmp/test.env
docker compose --env-file /tmp/test.env -f docker/docker-compose.yml --profile ollama config -q

# Console sans Docker de production : lancer l'application contre le démon local
cd docker/container-manager
pip install -r requirements.txt
SOC_ADMIN_PASSWORD=test uvicorn app:app --port 8801
# puis http://127.0.0.1:8801 (admin / test)

# Syntaxe
python3 -m py_compile docker/container-manager/*.py docker/green-arrow/*.py docker/oracle/tool_cli.py
node --check docker/container-manager/static/app.js
bash -n justice.sh docker/*/start.sh
```

## Tests réalisés et limites

Réalisés pendant le développement (environnement Linux x86_64, conteneurs de test avec les vrais scripts) :

- Console : authentification, blocage des identifiants invalides, refus CSRF, liste/détails/statistiques de conteneurs, actions pause/reprise/redémarrage, refus d'actions inconnues, journaux ;
- Outils : audit local, refus d'une IP hors périmètre, rejet d'une injection dans une IP ou un domaine, ajout/retrait de domaine OSINT, refus d'un doublon d'action, listing, lecture, téléchargement et refus de traversée de chemin ;
- Interface : chargement de toutes les vues sans erreur JavaScript, thèmes clair/sombre, mobile ;
- `docker compose config` avec et sans le profil `ollama` ; vérification de la disponibilité de wheels `aarch64` pour les dépendances Python.

**Non réalisés** (à valider au premier déploiement) : construction complète des images (accès aux registres impossible dans l'environnement de rédaction), exécution sur matériel ARM64/Apple Silicon, découverte ARP réelle, flux complet Suricata/Zeek/Wazuh → MARTIAN → notifications, import du workflow n8n, restauration de sauvegarde.

## Pistes d'amélioration connues

- Épingler les versions des images `latest` (n8n, ollama) et des outils Go du Bug Bounty Lab.
- Publier des images multi-arch pré-construites (`docker buildx`) pour éviter la compilation locale.
- Option `network_mode: host` documentée pour GREEN ARROW sous Linux.
- Persistance de l'historique des tâches de la Console (aujourd'hui en mémoire).
- Session SOC en `secure=True` et `N8N_SECURE_COOKIE=true` derrière HTTPS.
- Purge/rétention configurable des bases MARTIAN/SOC.
- Résumés IA de `veille_cyber.py` via l'URL Ollama configurable (aujourd'hui `localhost:11434` codé en dur).

## Historique des évolutions récentes

| Évolution | Détail |
|---|---|
| Outils intégrés | Scanner de ports → `green-arrow`, OSINT → `oracle-cti`, veille cyber → `watchtower`, lancés au démarrage des conteneurs |
| Justice League Console | Remplace le Container Manager : tableau de bord, conteneurs, outils, tâches, inventaires |
| Compatibilité ARM64 / macOS | `LOG_ROOT` portable, profil `ollama` + `OLLAMA_URL`, build Bug Bounty tolérant, `justice.sh doctor` |
| Correctif | `bb-pipeline.sh` et les gabarits de rapport sont désormais copiés dans l'image du Bug Bounty Lab |
| Documentation | Ce dossier `docs/` |
