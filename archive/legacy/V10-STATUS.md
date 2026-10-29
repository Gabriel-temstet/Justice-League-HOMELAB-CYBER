# V10 STATUS

## Ajouts

- profil `lab` pour le conteneur Bug Bounty
- support des cibles privées sans allow-list préalable
- `bb-run --lab`
- pipeline `authorized|lab`
- audit des commandes
- documentation dédiée

## Sécurité de périmètre

Le mode lab ne supprime pas toute vérification : il limite l'exécution aux espaces privés/lab et aux noms locaux de développement. Les cibles Internet publiques restent soumises au profil autorisé.
