#!/bin/bash
# Demarre le scanner de decouverte historique ET les outils d'audit.
set -u
if [[ "${SERVICE_SCAN:-YES}" == "YES" ]]; then
  python3 /app/inventory.py &   # découverte + inventaire services (-sV) + vérification des prophéties
else
  bash /app/scanner.sh &        # découverte seule (ancien comportement)
fi
python3 /app/run_audits.py &
wait -n          # si l'un s'arrete, le conteneur sort et Docker le redemarre
exit $?
