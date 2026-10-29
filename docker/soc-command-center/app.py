
import os
from datetime import datetime, timezone
from typing import Any
import httpx
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="JUSTICE LEAGUE SOC COMMAND CENTER", version="7.0.0")
DB_DSN=os.getenv("MARTIAN_DB_DSN","postgresql://martian:martian@martian-db:5432/martian")
MARTIAN=os.getenv("MARTIAN_URL","http://martian-core:8787")
TOKEN=os.getenv("AI_GATEWAY_TOKEN","")

def db():
    return psycopg.connect(DB_DSN,row_factory=dict_row)

def auth(t):
    if TOKEN and t != TOKEN:
        raise HTTPException(status_code=401,detail="invalid token")

@app.get("/health")
def health():
    try:
        with db() as c:
            c.execute("SELECT 1")
        dbok=True
    except Exception:
        dbok=False
    return {"status":"ok" if dbok else "degraded","service":"SOC-COMMAND-CENTER",
            "version":"7.0.0","database":dbok}

@app.get("/api/overview")
def overview():
    with db() as c:
        events=c.execute("""SELECT COUNT(*) AS n FROM events
                            WHERE event_time > now()-interval '24 hours'""").fetchone()["n"]
        high=c.execute("""SELECT COUNT(*) AS n FROM events
                          WHERE severity IN ('high','critical')
                          AND event_time > now()-interval '24 hours'""").fetchone()["n"]
        investigations=c.execute("""SELECT COUNT(*) AS n FROM investigations
                                     WHERE status NOT IN ('closed','resolved')""").fetchone()["n"]
        assets=c.execute("""SELECT COUNT(*) AS n FROM entities
                           WHERE entity_type='asset'""").fetchone()["n"]
        indicators=c.execute("""SELECT COUNT(*) AS n FROM entities
                               WHERE entity_type='indicator'""").fetchone()["n"]
        sources=c.execute("""SELECT source,COUNT(*) AS n FROM events
                             WHERE event_time > now()-interval '24 hours'
                             GROUP BY source ORDER BY n DESC""").fetchall()
    return {"events_24h":events,"high_critical_24h":high,"open_investigations":investigations,
            "assets":assets,"indicators":indicators,"sources":sources}

@app.get("/api/events")
def api_events(limit:int=100):
    with db() as c:
        return {"items":c.execute(
            """SELECT id,event_type,source,severity,event_time,external_id,data
               FROM events ORDER BY event_time DESC LIMIT %s""",(min(limit,500),)
        ).fetchall()}

@app.get("/api/investigations")
def api_investigations():
    with db() as c:
        return {"items":c.execute(
            """SELECT id,title,status,priority,summary,created_at,updated_at
               FROM investigations ORDER BY updated_at DESC LIMIT 200"""
        ).fetchall()}

@app.get("/api/assets")
def api_assets():
    with db() as c:
        return {"items":c.execute(
            """SELECT external_id,data,first_seen,last_seen
               FROM entities WHERE entity_type='asset'
               ORDER BY last_seen DESC LIMIT 500"""
        ).fetchall()}

@app.get("/api/search")
def api_search(q:str,limit:int=50):
    pat=f"%{q}%"
    with db() as c:
        return {"items":c.execute(
            """SELECT id,event_type,source,severity,event_time,external_id,data
               FROM events WHERE data::text ILIKE %s OR COALESCE(external_id,'') ILIKE %s
               ORDER BY event_time DESC LIMIT %s""",(pat,pat,min(limit,200))
        ).fetchall()}

@app.get("/api/service-check")
async def service_check():
    targets={"martian":f"{MARTIAN}/health",
             "batman":"http://batman-normalizer:8790/health",
             "green_lantern":"http://green-lantern-v6:8899/health"}
    out={}
    async with httpx.AsyncClient(timeout=4) as c:
        for name,url in targets.items():
            try:
                r=await c.get(url); out[name]={"ok":r.is_success,"status":r.status_code}
            except Exception as e:
                out[name]={"ok":False,"error":str(e)}
    return out

@app.get("/",response_class=HTMLResponse)
def index():
    return HTML

HTML=r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Justice League — SOC Command Center</title>
<style>
:root{--bg:#071018;--panel:#0d1923;--line:#1b3345;--txt:#e7f1f7;--muted:#8ea6b7;--accent:#56c7ff}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#050a0f,#091824);color:var(--txt);font:14px system-ui}
header{padding:18px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}
h1{margin:0;font-size:20px}.wrap{padding:20px;max-width:1500px;margin:auto}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px}
.num{font-size:28px;font-weight:700;margin-top:7px}.muted{color:var(--muted)}
.cols{display:grid;grid-template-columns:1.5fr 1fr;gap:14px;margin-top:14px}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}
.badge{padding:3px 7px;border-radius:8px;background:#173041}.high{color:#ffcc66}.critical{color:#ff6b6b}
input{background:#08141d;color:var(--txt);border:1px solid var(--line);padding:9px;border-radius:8px;width:100%}
pre{white-space:pre-wrap;color:#a9c7d8}.ok{color:#73e6a2}.bad{color:#ff7777}
@media(max-width:1000px){.grid,.cols{grid-template-columns:1fr 1fr}}@media(max-width:650px){.grid,.cols{grid-template-columns:1fr}}
</style></head>
<body><header><h1>🛡️ JUSTICE LEAGUE — SOC COMMAND CENTER</h1><span id="clock" class="muted"></span></header>
<div class="wrap">
<div class="grid">
<div class="card"><span class="muted">Événements 24h</span><div id="events" class="num">—</div></div>
<div class="card"><span class="muted">High / Critical</span><div id="high" class="num">—</div></div>
<div class="card"><span class="muted">Investigations ouvertes</span><div id="inv" class="num">—</div></div>
<div class="card"><span class="muted">Assets</span><div id="assets" class="num">—</div></div>
<div class="card"><span class="muted">Indicators</span><div id="inds" class="num">—</div></div>
</div>
<div class="card" style="margin-top:14px"><input id="q" placeholder="Rechercher un événement, IOC, IP, hostname..." onkeydown="if(event.key==='Enter')search()"></div>
<div class="cols">
<div class="card"><h3>Flux événements</h3><table><thead><tr><th>Heure</th><th>Source</th><th>Sévérité</th><th>Type</th><th>External ID</th></tr></thead><tbody id="eventRows"></tbody></table></div>
<div class="card"><h3>Investigations</h3><table><thead><tr><th>Priorité</th><th>Titre</th><th>Statut</th></tr></thead><tbody id="invRows"></tbody></table>
<h3>Services</h3><pre id="services">—</pre></div>
</div></div>
<script>
const $=x=>document.getElementById(x);
function esc(x){return String(x??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function j(u){let r=await fetch(u);return r.json()}
async function refresh(){
 let o=await j('/api/overview'); $('events').textContent=o.events_24h;$('high').textContent=o.high_critical_24h;
 $('inv').textContent=o.open_investigations;$('assets').textContent=o.assets;$('inds').textContent=o.indicators;
 let e=await j('/api/events?limit=50');$('eventRows').innerHTML=e.items.map(x=>`<tr><td>${esc(x.event_time)}</td><td>${esc(x.source)}</td><td class="${x.severity==='critical'?'critical':x.severity==='high'?'high':''}">${esc(x.severity)}</td><td>${esc(x.event_type)}</td><td>${esc(x.external_id)}</td></tr>`).join('');
 let i=await j('/api/investigations');$('invRows').innerHTML=i.items.slice(0,30).map(x=>`<tr><td>${esc(x.priority)}</td><td>${esc(x.title)}</td><td>${esc(x.status)}</td></tr>`).join('');
 let s=await j('/api/service-check');$('services').textContent=JSON.stringify(s,null,2);
}
async function search(){let q=$('q').value.trim();if(!q)return refresh();let e=await j('/api/search?q='+encodeURIComponent(q));$('eventRows').innerHTML=e.items.map(x=>`<tr><td>${esc(x.event_time)}</td><td>${esc(x.source)}</td><td>${esc(x.severity)}</td><td>${esc(x.event_type)}</td><td>${esc(x.external_id)}</td></tr>`).join('')}
setInterval(()=>{$('clock').textContent=new Date().toLocaleString('fr-FR')},1000);setInterval(refresh,15000);refresh();
</script></body></html>"""
