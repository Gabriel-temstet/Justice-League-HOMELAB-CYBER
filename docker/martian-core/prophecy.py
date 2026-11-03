"""Prophéties : bus de décision entre ORACLE (qui prédit) et GREEN ARROW / HAWKMAN /
GREEN LANTERN (qui agissent). Une prophétie = « tel risque va probablement se
matérialiser sur tel actif avant telle date », avec sa base de calcul.

Cycle de vie :
  open          publiée par ORACLE
  confirmed     GREEN ARROW a revérifié sur l'actif : le service vulnérable est bien exposé
  refuted       GREEN ARROW a revérifié : service absent ou version corrigée
  notified      un humain a été prévenu (GREEN LANTERN)
  acknowledged  un humain a pris acte (accepté, en cours)
  resolved      ORACLE ne la reproduit plus (corrigé / retiré)
Toutes ces actions sont passives ou en lecture seule : aucune remédiation automatique.
"""
import os
import hmac
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

import memory

TOKEN = os.getenv("AI_GATEWAY_TOKEN", "")
VALID_STATUS = {"open", "confirmed", "refuted", "notified", "acknowledged", "resolved"}
router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS prophecies (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    cve TEXT,
    asset TEXT,
    port INTEGER,
    title TEXT NOT NULL,
    probability NUMERIC(5,4) NOT NULL DEFAULT 0,
    priority NUMERIC(6,2) NOT NULL DEFAULT 0,
    basis TEXT NOT NULL DEFAULT 'model',
    deadline TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'open',
    rationale JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    notified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_prophecies_status ON prophecies(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_prophecies_asset ON prophecies(asset);
"""


def init_db():
    with memory.conn() as c:
        c.execute(SCHEMA)
        c.commit()


def auth(tok: str | None):
    if TOKEN and not (tok and hmac.compare_digest(tok, TOKEN)):
        raise HTTPException(status_code=401, detail="invalid token")


class ProphecyIn(BaseModel):
    key: str = Field(min_length=3, max_length=300)
    kind: str = "cve"                  # cve | osint
    cve: Optional[str] = None
    asset: Optional[str] = None
    port: Optional[int] = None
    title: str
    probability: float = Field(0, ge=0, le=1)
    priority: float = Field(0, ge=0, le=100)
    basis: str = "model"               # model (EPSS/KEV) | rule (règle déterministe)
    deadline: Optional[datetime] = None
    rationale: dict[str, Any] = Field(default_factory=dict)


class ProphecyPatch(BaseModel):
    status: Optional[str] = None
    mark_notified: bool = False
    evidence: Optional[dict[str, Any]] = None   # ajouté à l'historique, jamais écrasé


@router.post("/prophecies")
def publish(p: ProphecyIn, x_ai_gateway_token: str | None = Header(default=None)):
    """Crée ou rafraîchit une prophétie (idempotent sur `key`).
    Une prophétie `resolved`/`refuted` qui réapparaît est rouverte."""
    auth(x_ai_gateway_token)
    with memory.conn() as c:
        row = c.execute(
            """INSERT INTO prophecies(key,kind,cve,asset,port,title,probability,priority,basis,deadline,rationale)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(key) DO UPDATE SET
                 title=EXCLUDED.title, probability=EXCLUDED.probability, priority=EXCLUDED.priority,
                 basis=EXCLUDED.basis, deadline=EXCLUDED.deadline, rationale=EXCLUDED.rationale,
                 updated_at=now(),
                 status=CASE WHEN prophecies.status IN ('resolved','refuted') THEN 'open' ELSE prophecies.status END,
                 notified_at=CASE WHEN prophecies.status IN ('resolved','refuted') THEN NULL ELSE prophecies.notified_at END
               RETURNING *, (xmax = 0) AS created""",
            (p.key, p.kind, p.cve, p.asset, p.port, p.title[:300], p.probability, p.priority,
             p.basis, p.deadline, Jsonb(p.rationale)),
        ).fetchone()
        c.commit()
    return row


@router.get("/prophecies")
def list_prophecies(status: str = "", kind: str = "", asset: str = "", min_priority: float = 0,
                    limit: int = 200, x_ai_gateway_token: str | None = Header(default=None)):
    """`status` accepte une liste séparée par des virgules (ex. open,confirmed)."""
    auth(x_ai_gateway_token)
    where, args = ["priority >= %s"], [min_priority]
    st = [s for s in status.split(",") if s]
    if st:
        bad = [s for s in st if s not in VALID_STATUS]
        if bad:
            raise HTTPException(422, f"statut inconnu: {bad}")
        where.append("status = ANY(%s)")
        args.append(st)
    if kind:
        where.append("kind = %s")
        args.append(kind)
    if asset:
        where.append("asset = %s")
        args.append(asset)
    args.append(max(1, min(limit, 1000)))
    with memory.conn() as c:
        rows = c.execute(
            f"SELECT * FROM prophecies WHERE {' AND '.join(where)} ORDER BY priority DESC, updated_at DESC LIMIT %s",
            args).fetchall()
    return {"prophecies": rows}


@router.patch("/prophecies/{pid}")
def update(pid: int, patch: ProphecyPatch, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    if patch.status and patch.status not in VALID_STATUS:
        raise HTTPException(422, f"statut inconnu: {patch.status}")
    with memory.conn() as c:
        row = c.execute(
            """UPDATE prophecies SET
                 status=COALESCE(%s,status),
                 notified_at=CASE WHEN %s THEN now() ELSE notified_at END,
                 evidence=CASE WHEN %s::jsonb IS NULL THEN evidence
                               ELSE evidence || jsonb_build_array(%s::jsonb || jsonb_build_object('at', now())) END,
                 updated_at=now()
               WHERE id=%s RETURNING *""",
            (patch.status, patch.mark_notified,
             Jsonb(patch.evidence) if patch.evidence else None,
             Jsonb(patch.evidence) if patch.evidence else None, pid)).fetchone()
        c.commit()
    if not row:
        raise HTTPException(404, "prophecy not found")
    return row


@router.get("/inventory")
def inventory(limit: int = 2000, x_ai_gateway_token: str | None = Header(default=None)):
    """Inventaire services/versions publié par GREEN ARROW (entités `asset_services`)."""
    auth(x_ai_gateway_token)
    with memory.conn() as c:
        rows = c.execute(
            "SELECT external_id AS asset, data, last_seen FROM entities WHERE entity_type='asset_services' "
            "ORDER BY last_seen DESC LIMIT %s", (max(1, min(limit, 5000)),)).fetchall()
    return {"assets": [{"asset": r["asset"], "last_seen": r["last_seen"], **r["data"]} for r in rows]}
