#!/bin/bash
# Demarre le scanner de decouverte historique ET les outils d'audit.
set -u
bash /app/scanner.sh &
python3 /app/run_audits.py &
wait -n          # si l'un s'arrete, le conteneur sort et Docker le redemarre
exit $?
