# Justice League Homelab V5

## Ce qui est réellement ajouté

1. MARTIAN-MANHUNTER dispose d'une mémoire PostgreSQL persistante.
2. Les événements, entités et relations ont un schéma dédié.
3. Les événements peuvent être recherchés dans l'historique.
4. Les investigations ont un identifiant et un cycle de vie persistant.
5. `/correlate` peut croiser alerte, assets, CVE, CTI et historique.
6. L'IA reçoit un paquet d'évidence déterministe et doit distinguer faits,
   corrélations, hypothèses et éléments manquants.

## Limite assumée

Les connecteurs Wazuh/Zeek/Suricata → BATMAN et les enrichissements SUPERMAN/ORACLE
doivent être câblés dans n8n pour chaque environnement. V5 fournit le contrat API et
la mémoire, mais ne prétend pas avoir découvert automatiquement tous les formats
d'événements de votre infrastructure.
