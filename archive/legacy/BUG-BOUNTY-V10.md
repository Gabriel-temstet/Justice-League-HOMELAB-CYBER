# Bug Bounty Lab — V10

Le conteneur Bug Bounty possède deux profils :

- `authorized` : cible Internet ou autre cible déclarée dans `/scope/targets.json`.
- `lab` : cible de laboratoire privée, sans obligation d'inscription dans `targets.json`.

Le profil `lab` reconnaît notamment `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, localhost, les link-local et IPv6 ULA, ainsi que les suffixes `.local`, `.test`, `.internal`, `.home` et `.lan`.

## Utilisation

Depuis l'hôte :

```bash
./scripts/bug-bounty-pipeline.sh app.test passive lab
./scripts/bug-bounty-pipeline.sh 192.168.50.20 active lab
./scripts/bug-bounty-pipeline.sh target.example passive authorized
```

Dans le conteneur :

```bash
bb-run --lab nmap -sV 192.168.50.20
bb-run --lab httpx -u http://app.test
```

Toutes les commandes lancées via `bb-run` sont ajoutées à `/results/command-audit.log`.

Le profil `lab` n'est pas une autorisation pour scanner des hôtes publics : il est destiné aux environnements privés/laboratoire. Les cibles publiques restent dans le profil `authorized` avec un scope explicite.
