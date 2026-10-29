import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import memory

app = FastAPI(title="MARTIAN-MANHUNTER V5", version="5.0.0")
TOKEN = os.getenv("AI_GATEWAY_TOKEN", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

class EventIn(BaseModel):
    event_type: str = "security"
    source: str = "unknown"
    severity: str = "info"
    event_time: Optional[datetime] = None
    external_id: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)

class EntityIn(BaseModel):
    entity_type: str
    external_id: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)

class CorrelateIn(BaseModel):
    alert: dict[str, Any]
    assets: list[dict[str, Any]] = []
    cves: list[dict[str, Any]] = []
    cti: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    ask_ai: bool = True

class InvestigateIn(BaseModel):
    title: str
    query: str = ""
    priority: str = "medium"

@app.on_event("startup")
def startup():
    memory.init_db()

def auth(x_ai_gateway_token: str | None):
    if TOKEN and x_ai_gateway_token != TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

@app.get("/health")
def health():
    return {"status": "ok", "service": "MARTIAN-MANHUNTER", "version": "5.0.0"}

@app.post("/memory/entity")
def ingest_entity(payload: EntityIn, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    return memory.upsert_entity(payload.entity_type, payload.external_id, payload.data)

@app.post("/memory/event")
def ingest_event(payload: EventIn, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    t = payload.event_time or datetime.now(timezone.utc)
    return memory.insert_event(
        payload.event_type, payload.source, payload.severity, t,
        payload.external_id, payload.data
    )

@app.get("/memory/events")
def events(limit: int = 100, source: str | None = None, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    return {"events": memory.recent_events(min(limit, 500), source)}

@app.get("/memory/search")
def search(q: str, limit: int = 50, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    return {"events": memory.search_events(q, min(limit, 200))}

@app.get("/memory/entity/{entity_type}/{external_id:path}")
def entity(entity_type: str, external_id: str, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    item = memory.get_entity(entity_type, external_id)
    if not item:
        raise HTTPException(status_code=404, detail="entity not found")
    return {"entity": item, "relationships": memory.related(entity_type, external_id)}

async def ai_interpret(correlation: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
You are MARTIAN-MANHUNTER, a defensive SOC analysis assistant.
Analyze ONLY the evidence below. Never claim compromise without evidence.
Never invent asset ownership, versions, exploits, history, or CTI.
Return strict JSON with keys:
confirmed_facts, correlations, hypotheses, missing_evidence, safe_next_steps.
Sensitive remediation or disruptive actions require human approval.

EVIDENCE:
{correlation}
"""
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "format": "json"}
            )
            r.raise_for_status()
            import json
            return json.loads(r.json().get("response", "{}"))
    except Exception as e:
        return {"error": "AI interpretation unavailable", "detail": str(e)}


class NormalizedEvent(BaseModel):
    source: str
    event_type: str
    severity: str = "info"
    timestamp: Optional[datetime] = None
    external_id: Optional[str] = None
    asset_ids: list[str] = []
    indicators: list[str] = []
    data: dict[str, Any] = Field(default_factory=dict)

@app.post("/ingest")
def ingest(payload: NormalizedEvent, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    t=payload.timestamp or datetime.now(timezone.utc)
    ev=memory.insert_event(payload.event_type,payload.source,payload.severity,t,payload.external_id,
                           {**payload.data,"asset_ids":payload.asset_ids,"indicators":payload.indicators})
    for aid in payload.asset_ids:
        memory.upsert_relationship("event",str(ev["id"]),"affects","asset",aid,0.95,{"source":payload.source})
    for ind in payload.indicators:
        memory.upsert_entity("indicator",ind,{"indicator":ind})
        memory.upsert_relationship("event",str(ev["id"]),"contains","indicator",ind,0.90,{"source":payload.source})
    return {"status":"ingested","event":ev}

@app.get("/investigations")
def investigations(limit:int=100,status:str|None=None,x_ai_gateway_token:str|None=Header(default=None)):
    auth(x_ai_gateway_token)
    return {"investigations":memory.list_investigations(min(limit,500),status)}

class InvestigationUpdate(BaseModel):
    status: Optional[str]=None
    priority: Optional[str]=None
    summary: Optional[str]=None

@app.patch("/investigations/{investigation_id}")
def patch_investigation(investigation_id:str,payload:InvestigationUpdate,
                        x_ai_gateway_token:str|None=Header(default=None)):
    auth(x_ai_gateway_token)
    row=memory.update_investigation(investigation_id,payload.status,payload.priority,payload.summary)
    if not row: raise HTTPException(status_code=404,detail="investigation not found")
    return row

@app.post("/correlate")
async def correlate(payload: CorrelateIn, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    alert = payload.alert
    ip_values = {str(alert.get(k)) for k in ("src_ip","dst_ip","source_ip","destination_ip") if alert.get(k)}
    indicator_values = {str(alert.get(k)) for k in ("indicator","domain","url","hash") if alert.get(k)}

    matches = []
    for a in payload.assets:
        aid = str(a.get("id") or a.get("asset_id") or a.get("hostname") or a.get("ip") or "")
        vals = {str(a.get(k)) for k in ("ip","hostname","asset_id","id") if a.get(k)}
        if ip_values & vals:
            matches.append({"type":"alert_to_asset","asset":aid,"evidence":list(ip_values & vals)})

    for c in payload.cves:
        product = str(c.get("product") or c.get("package") or "")
        version = str(c.get("version") or "")
        alert_text = str(alert).lower()
        if product and product.lower() in alert_text:
            matches.append({"type":"alert_to_cve","cve":c.get("id"),"product":product,"version":version})

    for t in payload.cti:
        vals = {str(t.get(k)) for k in ("indicator","domain","url","hash","ip","cve") if t.get(k)}
        if indicator_values & vals:
            matches.append({"type":"alert_to_cti","indicator_match":list(indicator_values & vals),"cti":t})

    history_matches = []
    for h in payload.history:
        hvals = {str(h.get(k)) for k in ("src_ip","dst_ip","source_ip","destination_ip","ip","indicator") if h.get(k)}
        if ip_values & hvals:
            history_matches.append(h)
    if history_matches:
        matches.append({"type":"alert_to_history","count":len(history_matches)})

    score = min(100, len(matches)*20 + (20 if history_matches else 0))
    severity = "critical" if score >= 80 else "high" if score >= 60 else "medium" if score >= 30 else "low"
    package = {
        "alert": alert,
        "evidence_counts": {
            "assets": len(payload.assets), "cves": len(payload.cves),
            "cti": len(payload.cti), "history": len(payload.history)
        },
        "matches": matches,
        "history_matches": history_matches[:50],
        "correlation_score": score,
        "severity": severity,
        "human_approval_required": severity in ("high","critical")
    }
    if payload.ask_ai:
        package["ai_assessment"] = await ai_interpret(package)
    return package

@app.post("/investigations")
def investigation(payload: InvestigateIn, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    iid = str(uuid.uuid4())
    with memory.conn() as c:
        row = c.execute(
            """INSERT INTO investigations(id,title,status,priority,summary,data)
               VALUES(%s,%s,'open',%s,%s,%s) RETURNING *""",
            (iid, payload.title, payload.priority, payload.query, {"query": payload.query})
        ).fetchone()
        c.commit()
    return row

@app.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str, x_ai_gateway_token: str | None = Header(default=None)):
    auth(x_ai_gateway_token)
    with memory.conn() as c:
        inv = c.execute("SELECT * FROM investigations WHERE id=%s", (investigation_id,)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="investigation not found")
        evs = c.execute(
            """SELECT e.* FROM events e
               JOIN investigation_events ie ON ie.event_id=e.id
               WHERE ie.investigation_id=%s ORDER BY e.event_time DESC""",
            (investigation_id,)
        ).fetchall()
    return {"investigation": inv, "events": evs}
