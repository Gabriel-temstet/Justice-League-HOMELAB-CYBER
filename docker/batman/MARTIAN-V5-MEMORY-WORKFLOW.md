# MARTIAN-MANHUNTER V5 — mémoire et investigations

## Flux recommandé

Wazuh / Zeek / Suricata
→ BATMAN normalise l'événement
→ POST `/memory/event`
→ enrichissement SUPERMAN (asset/CPE/CVE)
→ enrichissement ORACLE (CTI/CERT-FR/CISA)
→ recherche `/memory/search` sur historique
→ POST `/correlate`
→ MARTIAN produit faits/corrélations/hypothèses
→ GREEN LANTERN notifie Discord/WhatsApp
→ si HIGH/CRITICAL: investigation humaine

## Mémoire

- `entities`: assets, CVE, indicateurs, équipements, services.
- `events`: événements bruts/normalisés avec horodatage.
- `relationships`: relations observées entre entités.
- `investigations`: dossiers persistants.
- `investigation_events`: événements rattachés à une investigation.

## Principe

La mémoire est une source d'évidence, pas une vérité implicite. Une corrélation historique
ne prouve pas une compromission. Toute action disruptive ou corrective sensible reste soumise
à validation humaine.
