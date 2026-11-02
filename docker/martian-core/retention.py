"""Rétention des événements MARTIAN : en ligne -> archive -> purge.

  - en ligne  : table `events`          (RETENTION_ONLINE_DAYS, défaut 90 j)
  - archive   : table `events_archive`  (RETENTION_ARCHIVE_DAYS, défaut 180 j *après* la période en ligne)
  - au-delà   : suppression définitive

Les âges sont calculés sur `event_time`. Les événements rattachés à une enquête
(`investigation_events`) ou à un dossier SOC (`soc_case_events`) ne sont jamais
archivés ni purgés : les supprimer ferait disparaître le lien (ON DELETE CASCADE).
"""
import logging
import os
import threading
import time

import memory

log = logging.getLogger("martian.retention")


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


ENABLED = os.getenv("RETENTION_ENABLED", "YES").strip().upper() in ("YES", "TRUE", "1")
ONLINE_DAYS = _env_int("RETENTION_ONLINE_DAYS", 90)
ARCHIVE_DAYS = _env_int("RETENTION_ARCHIVE_DAYS", 180)
INTERVAL_HOURS = _env_int("RETENTION_INTERVAL_HOURS", 6)
BATCH = _env_int("RETENTION_BATCH", 5000)

_lock = threading.Lock()
_last: dict = {}


def _protected_sql(c) -> str:
    """Condition SQL (alias `e`) : l'événement n'est rattaché à aucune enquête/dossier."""
    parts = ["NOT EXISTS (SELECT 1 FROM investigation_events ie WHERE ie.event_id = e.id)"]
    # soc_case_events est créée par le service SOC, éventuellement après martian-core.
    if c.execute("SELECT to_regclass('public.soc_case_events') IS NOT NULL AS ok").fetchone()["ok"]:
        parts.append("NOT EXISTS (SELECT 1 FROM soc_case_events ce WHERE ce.event_id = e.id)")
    return " AND ".join(parts)


def _archive_batch(c, protected: str) -> int:
    row = c.execute(
        f"""
        WITH batch AS (
            SELECT e.id FROM events e
            WHERE e.event_time < now() - make_interval(days => %(d)s) AND {protected}
            ORDER BY e.event_time
            LIMIT %(n)s
            FOR UPDATE OF e SKIP LOCKED
        ), moved AS (
            DELETE FROM events WHERE id IN (SELECT id FROM batch) RETURNING *
        ), ins AS (
            INSERT INTO events_archive(id,event_type,source,severity,event_time,external_id,data,created_at)
            SELECT id,event_type,source,severity,event_time,external_id,data,created_at FROM moved
            ON CONFLICT (id) DO NOTHING
        ), rel AS (
            -- liens événement->actif/indicateur : l'info reste dans events_archive.data
            DELETE FROM relationships WHERE left_type='event' AND left_id IN (SELECT id::text FROM moved)
        )
        SELECT count(*) AS n FROM moved
        """,
        {"d": ONLINE_DAYS, "n": BATCH},
    ).fetchone()
    c.commit()
    return row["n"]


def _purge_batch(c) -> int:
    cur = c.execute(
        """
        DELETE FROM events_archive WHERE id IN (
            SELECT id FROM events_archive
            WHERE event_time < now() - make_interval(days => %(d)s)
            ORDER BY event_time LIMIT %(n)s)
        """,
        {"d": ONLINE_DAYS + ARCHIVE_DAYS, "n": BATCH},
    )
    c.commit()
    return cur.rowcount


def status() -> dict:
    with memory.conn() as c:
        protected = _protected_sql(c)
        online = c.execute("SELECT count(*) n, min(event_time) oldest FROM events").fetchone()
        arch = c.execute("SELECT count(*) n, min(event_time) oldest FROM events_archive").fetchone()
        due_archive = c.execute(
            f"SELECT count(*) n FROM events e WHERE e.event_time < now() - make_interval(days => %s) AND {protected}",
            (ONLINE_DAYS,),
        ).fetchone()["n"]
        held = c.execute(
            f"SELECT count(*) n FROM events e WHERE e.event_time < now() - make_interval(days => %s) AND NOT ({protected})",
            (ONLINE_DAYS,),
        ).fetchone()["n"]
        due_purge = c.execute(
            "SELECT count(*) n FROM events_archive WHERE event_time < now() - make_interval(days => %s)",
            (ONLINE_DAYS + ARCHIVE_DAYS,),
        ).fetchone()["n"]
    return {
        "enabled": ENABLED,
        "policy": {"online_days": ONLINE_DAYS, "archive_days": ARCHIVE_DAYS,
                   "total_days": ONLINE_DAYS + ARCHIVE_DAYS, "interval_hours": INTERVAL_HOURS},
        "online": {"events": online["n"], "oldest": online["oldest"]},
        "archive": {"events": arch["n"], "oldest": arch["oldest"]},
        "pending": {"to_archive": due_archive, "to_purge": due_purge,
                    "held_by_case_or_investigation": held},
        "last_run": _last or None,
    }


def run_once(dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, **status()["pending"]}
    if not _lock.acquire(blocking=False):
        return {"skipped": "already running"}
    try:
        archived = purged = 0
        with memory.conn() as c:
            protected = _protected_sql(c)
            while (n := _archive_batch(c, protected)):
                archived += n
            while (n := _purge_batch(c)):
                purged += n
        _last.clear()
        _last.update({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "archived": archived, "purged": purged})
        log.info("retention: %s archived, %s purged", archived, purged)
        return {"dry_run": False, "archived": archived, "purged": purged}
    finally:
        _lock.release()


def _loop():
    time.sleep(60)  # laisse le temps au schéma / au service SOC de démarrer
    while True:
        try:
            run_once()
        except Exception:  # la boucle ne doit jamais s'arrêter
            log.exception("retention run failed")
        time.sleep(INTERVAL_HOURS * 3600)


def start():
    if not ENABLED:
        log.info("retention disabled (RETENTION_ENABLED=NO)")
        return
    threading.Thread(target=_loop, name="retention", daemon=True).start()
