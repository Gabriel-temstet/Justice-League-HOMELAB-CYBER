# 4. Console web (Justice League Console)

Interface de gestion Docker **et** de lancement des outils intégrés. Elle remplace le « Container Manager » d'origine.

- URL : **http://127.0.0.1:8801**
- Connexion : fenêtre d'authentification du navigateur (Basic Auth) avec `SOC_ADMIN_USER` / `SOC_ADMIN_PASSWORD`.
- Interface : thème sombre/clair (bouton en haut à droite, mémorisé), adaptée au mobile, sans dépendance externe (aucun CDN).

## Navigation

### Tableau de bord
Vue d'ensemble : conteneurs actifs/total, CPU total (avec courbe), mémoire, réseau cumulé, **tuiles de la stack** par codename (cliquer ouvre le détail), **alertes** (conteneurs *unhealthy*, qui redémarrent en boucle ou arrêtés avec un code d'erreur), informations de l'hôte Docker (dont l'architecture), accès rapide aux outils. Actualisation automatique toutes les 5 s.

### Conteneurs
Tableau filtrable (nom, codename, image, port) et triable (nom, CPU, mémoire, état), filtres Tous/Actifs/Arrêtés. Par ligne : état, CPU, mémoire, ports, âge, boutons **démarrer / redémarrer / arrêter**. Un clic ouvre le **tiroir de détail** :

- **Aperçu** : CPU, mémoire, réseau, processus, image, politique de redémarrage, utilisateur, ports, réseaux (IP), volumes, durcissement (lecture seule, capabilities), derniers contrôles de santé. Boutons redémarrer / pause / reprise / arrêter.
- **Journaux** : suivi en direct (rafraîchi toutes les 2 s), coloration des erreurs/avertissements, filtre texte, case « Suivre », téléchargement.
- **Configuration** : entrypoint, commande, variables d'environnement. Les valeurs dont le nom contient `PASS`, `TOKEN`, `KEY`, `SECRET`, `DSN`, `WEBHOOK`, `AUTH` (sauf `AUTHORIZED_*`) ou `CREDENTIAL` sont **masquées**.

La Console refuse de s'arrêter ou de se mettre en pause elle-même.

### Outils
Une carte par outil (GREEN ARROW, ORACLE, WATCHTOWER) avec : état du conteneur, avertissement d'usage légal, **boutons d'action**, et un **navigateur de fichiers** des résultats (dossiers, aperçu, téléchargement ; les CSV sont affichés en tableau).

Lancer une action :
1. Cliquer sur l'action ; si elle a des paramètres, un formulaire s'ouvre (sous-réseau, IP, domaine…).
2. Les actions risquées demandent une confirmation.
3. Une fenêtre affiche la **sortie en direct** et l'état (en cours / terminé / échec / délai dépassé).
4. À la fin, la liste des fichiers est rafraîchie.

Catalogue des actions : voir [Outils intégrés](05-outils-integres.md).

### Tâches
Historique des actions d'outils (60 dernières, en mémoire : perdu au redémarrage de la Console) avec paramètres, état, durée, utilisateur. Cliquer rouvre la sortie.

### Images / Volumes / Réseaux
Inventaires en lecture seule : images (taille, conteneurs utilisateurs, inutilisées), volumes (orphelins), réseaux (sous-réseau, conteneurs).

## Sécurité de la Console

| Mesure | Détail |
|---|---|
| Exposition | Port lié à `127.0.0.1`. Accès distant : VPN ou tunnel SSH |
| Authentification | Basic Auth ; **8 échecs en 2 minutes par IP → blocage 429** |
| CSRF | Toute requête non-GET exige l'en-tête `X-JLC: 1` (impossible à forger depuis un autre site) |
| En-têtes | CSP stricte (`default-src 'self'`), `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, `no-store` |
| Pas de shell libre | Seules les actions Docker explicites (démarrer, arrêter, redémarrer, pause, reprise) et les commandes **en liste blanche** de `tools.py` sont exécutables, avec paramètres validés (liste de commandes, jamais de shell) |
| Périmètre des scans | Vérifié deux fois : par la Console (format) et par l'outil dans le conteneur (`AUTHORIZED_CIDRS`) |
| Fichiers | Chemins limités à des dossiers prédéfinis, segments `[A-Za-z0-9._-]`, profondeur ≤ 3, lecture ≤ 400 Ko en aperçu |
| Audit | Chaque action est journalisée : `docker logs justice-league-container-manager \| grep AUDIT` |
| Durcissement | Conteneur en lecture seule, `cap_drop: ALL`, `no-new-privileges` |

> **Le socket Docker équivaut à un accès root à l'hôte.** Mot de passe fort et unique, jamais d'exposition Internet.

## Ajouter un outil à la Console

Les outils sont décrits dans `docker/container-manager/tools.py` (dictionnaire `TOOLS`). Chaque outil définit : `container`, `actions`, `files`, éventuellement `sources` (listes dynamiques) et `link`. Une action contient :

```python
{"id": "discover", "label": "Découverte réseau (ARP)", "desc": "…",
 "params": [{"name": "cidr", "label": "Sous-réseau", "type": "select", "source": "cidrs"}],
 "timeout": 300,                    # secondes, appliqué avec `timeout` dans le conteneur
 "danger": False, "confirm": "…",   # confirmation facultative
 "build": lambda p: (["python3", "/app/tool_cli.py", "discover", _cidr(p["cidr"])], {})}  # (argv, env)
```

Règles : `build` renvoie une **liste d'arguments** (jamais une chaîne shell), valide chaque paramètre (`_ip`, `_cidr`, `_domain`) et l'outil final doit **revalider** la cible. Aucun changement de l'interface n'est nécessaire : le catalogue est servi par `/api/tools` et rendu dynamiquement. Voir [Développement](10-developpement.md).
