#!/bin/sh
# Lance la veille cyber (boucle permanente) en parallele de l'API WATCHTOWER.
export VEILLE_DIR=/data/veille-cyber
mkdir -p "$VEILLE_DIR"
( while true; do python /app/veille-cyber/veille_cyber.py --intervalle "${VEILLE_INTERVALLE:-1800}"; sleep 30; done ) &
exec uvicorn app:app --host 0.0.0.0 --port 8830
