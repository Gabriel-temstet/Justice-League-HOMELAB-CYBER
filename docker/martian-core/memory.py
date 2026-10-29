import os
from datetime import datetime, timezone
from typing import Any
import psycopg
from psycopg.rows import dict_row

DB_DSN = os.getenv("MARTIAN_DB_DSN", "postgresql://martian:martian@martian-db:5432/martian")

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    external_id TEXT,
    data JSONB NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(entity_type, external_id)
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_last_seen ON entities(last_seen DESC);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT,
    severity TEXT,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    external_id TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_external ON events(external_id);

CREATE TABLE IF NOT EXISTS relationships (
    id BIGSERIAL PRIMARY KEY,
    left_type TEXT NOT NULL,
    left_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    right_type TEXT NOT NULL,
    right_id TEXT NOT NULL,
    confidence NUMERIC(5,4),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(left_type,left_id,relation,right_type,right_id)
);
CREATE INDEX IF NOT EXISTS idx_rel_left ON relationships(left_type,left_id);
CREATE INDEX IF NOT EXISTS idx_rel_right ON relationships(right_type,right_id);

CREATE TABLE IF NOT EXISTS investigations (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);

CREATE TABLE IF NOT EXISTS investigation_events (
    investigation_id UUID NOT NULL,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    PRIMARY KEY(investigation_id,event_id)
);
"""

def conn():
    return psycopg.connect(DB_DSN, row_factory=dict_row)

def init_db():
    with conn() as c:
        c.execute(SCHEMA)
        c.commit()

def upsert_entity(entity_type: str, external_id: str | None, data: dict[str, Any]):
    with conn() as c:
        row = c.execute(
            """INSERT INTO entities(entity_type,external_id,data)
               VALUES(%s,%s,%s)
               ON CONFLICT(entity_type,external_id)
               DO UPDATE SET data=EXCLUDED.data,last_seen=now()
               RETURNING *""",
            (entity_type, external_id, data)
        ).fetchone()
        c.commit()
        return row

def insert_event(event_type, source, severity, event_time, external_id, data):
    with conn() as c:
        row = c.execute(
            """INSERT INTO events(event_type,source,severity,event_time,external_id,data)
               VALUES(%s,%s,%s,%s,%s,%s) RETURNING *""",
            (event_type, source, severity, event_time, external_id, data)
        ).fetchone()
        c.commit()
        return row

def upsert_relationship(a_type,a_id,relation,b_type,b_id,confidence,evidence):
    with conn() as c:
        row = c.execute(
            """INSERT INTO relationships
               (left_type,left_id,relation,right_type,right_id,confidence,evidence)
               VALUES(%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(left_type,left_id,relation,right_type,right_id)
               DO UPDATE SET confidence=EXCLUDED.confidence,
                             evidence=EXCLUDED.evidence,last_seen=now()
               RETURNING *""",
            (a_type,a_id,relation,b_type,b_id,confidence,evidence)
        ).fetchone()
        c.commit()
        return row

def recent_events(limit=100, source=None):
    with conn() as c:
        if source:
            return c.execute(
                "SELECT * FROM events WHERE source=%s ORDER BY event_time DESC LIMIT %s",
                (source, limit)
            ).fetchall()
        return c.execute(
            "SELECT * FROM events ORDER BY event_time DESC LIMIT %s", (limit,)
        ).fetchall()

def search_events(q: str, limit=50):
    pattern = f"%{q}%"
    with conn() as c:
        return c.execute(
            """SELECT * FROM events
               WHERE data::text ILIKE %s
                  OR COALESCE(external_id,'') ILIKE %s
                  OR COALESCE(source,'') ILIKE %s
               ORDER BY event_time DESC LIMIT %s""",
            (pattern, pattern, pattern, limit)
        ).fetchall()

def get_entity(entity_type, external_id):
    with conn() as c:
        return c.execute(
            "SELECT * FROM entities WHERE entity_type=%s AND external_id=%s",
            (entity_type, external_id)
        ).fetchone()

def related(entity_type, external_id, limit=100):
    with conn() as c:
        return c.execute(
            """SELECT * FROM relationships
               WHERE (left_type=%s AND left_id=%s)
                  OR (right_type=%s AND right_id=%s)
               ORDER BY last_seen DESC LIMIT %s""",
            (entity_type, external_id, entity_type, external_id, limit)
        ).fetchall()

def list_investigations(limit=100, status=None):
    with conn() as c:
        if status:
            return c.execute("SELECT * FROM investigations WHERE status=%s ORDER BY updated_at DESC LIMIT %s",(status,limit)).fetchall()
        return c.execute("SELECT * FROM investigations ORDER BY updated_at DESC LIMIT %s",(limit,)).fetchall()

def update_investigation(iid, status=None, priority=None, summary=None):
    with conn() as c:
        row=c.execute("""UPDATE investigations SET
          status=COALESCE(%s,status), priority=COALESCE(%s,priority),
          summary=COALESCE(%s,summary), updated_at=now()
          WHERE id=%s RETURNING *""",(status,priority,summary,iid)).fetchone()
        c.commit()
        return row

def create_investigation(title, priority, summary, event_id=None):
    import uuid
    iid=str(uuid.uuid4())
    with conn() as c:
        c.execute("""INSERT INTO investigations(id,title,status,priority,summary,data)
          VALUES(%s,%s,'open',%s,%s,%s)""",
          (iid,title,priority,summary,{"created_from_event":event_id}))
        if event_id is not None:
            c.execute("INSERT INTO investigation_events(investigation_id,event_id) VALUES(%s,%s)",(iid,event_id))
        c.commit()
    return iid
