# MARTIAN V5 memory

PostgreSQL stores:

- `entities(entity_type, external_id, data, first_seen, last_seen)`
- `events(event_type, source, severity, event_time, external_id, data)`
- `relationships(left_type, left_id, relation, right_type, right_id, confidence, evidence)`
- `investigations(id, title, status, priority, summary, data)`
- `investigation_events(investigation_id, event_id)`

The model is intentionally evidence-oriented: observations are retained separately from
AI interpretation. This makes investigations reproducible and auditable.
