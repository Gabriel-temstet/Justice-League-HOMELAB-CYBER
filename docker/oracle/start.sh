#!/bin/sh
# Lance l'OSINT passif (boucle permanente) en parallele du collecteur CTI.
export HOME=/data/home            # l'outil ecrit dans $HOME/veille-osint
mkdir -p "$HOME"
for d in $(echo "${OSINT_DOMAINS:-}" | tr ',;' '  '); do
  python /app/osint/osint_veille.py --add "$d"
done
( while true; do python /app/osint/osint_veille.py --loop --hours "${OSINT_INTERVAL_HOURS:-6}"; sleep 60; done ) &
exec python /app/app.py
