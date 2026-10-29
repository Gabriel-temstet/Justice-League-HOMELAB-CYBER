import os, secrets, hashlib, json, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row
import httpx

DB=os.getenv('MARTIAN_DB_DSN','postgresql://martian:martian@martian-db:5432/martian')
ADMIN_USER=os.getenv('SOC_ADMIN_USER','admin')
ADMIN_PASSWORD=os.getenv('SOC_ADMIN_PASSWORD','CHANGE_ME')
MARTIAN_URL=os.getenv('MARTIAN_URL','http://martian-core:8787')
TOKEN=os.getenv('AI_GATEWAY_TOKEN','')
OLLAMA_URL=os.getenv('OLLAMA_URL','http://ollama:11434')
OLLAMA_MODEL=os.getenv('OLLAMA_MODEL','llama3.2:3b')
SESSIONS=set()
app=FastAPI(title='Justice League SOC Command Center',version='8.0.0')

SCHEMA='''
CREATE TABLE IF NOT EXISTS soc_cases(id UUID PRIMARY KEY,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',priority TEXT NOT NULL DEFAULT 'medium',summary TEXT,created_at TIMESTAMPTZ DEFAULT now(),updated_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS soc_case_events(case_id UUID REFERENCES soc_cases(id) ON DELETE CASCADE,event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,PRIMARY KEY(case_id,event_id));
CREATE TABLE IF NOT EXISTS soc_notes(id BIGSERIAL PRIMARY KEY,case_id UUID REFERENCES soc_cases(id) ON DELETE CASCADE,author TEXT NOT NULL,body TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS soc_audit(id BIGSERIAL PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT,details JSONB DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_soc_cases_updated ON soc_cases(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_soc_notes_case ON soc_notes(case_id,created_at DESC);
'''
def db(): return psycopg.connect(DB,row_factory=dict_row)
@app.on_event('startup')
def init():
    with db() as c: c.execute(SCHEMA); c.commit()
def logged(req:Request): return req.cookies.get('soc_session') in SESSIONS
def require(req:Request):
    if not logged(req): raise HTTPException(401,'authentication required')
def audit(actor,action,target='',details=None):
    with db() as c: c.execute('INSERT INTO soc_audit(actor,action,target,details) VALUES(%s,%s,%s,%s)',(actor,action,target,details or {})); c.commit()
class Login(BaseModel): user:str; password:str
class CaseIn(BaseModel): title:str; priority:str='medium'; summary:str=''
class CaseUpdate(BaseModel): status:str|None=None; priority:str|None=None; summary:str|None=None
class NoteIn(BaseModel): body:str
class AttachIn(BaseModel): event_id:int
class AskIn(BaseModel): question:str
@app.get('/health')
def health(): return {'status':'ok','service':'SOC-COMMAND-CENTER','version':'8.0.0'}
@app.post('/api/login')
def login(x:Login,response:Response):
    if not secrets.compare_digest(x.user,ADMIN_USER) or not secrets.compare_digest(x.password,ADMIN_PASSWORD): raise HTTPException(401,'invalid credentials')
    s=secrets.token_urlsafe(32); SESSIONS.add(s); response.set_cookie('soc_session',s,httponly=True,samesite='strict',secure=False,max_age=28800); audit(x.user,'login'); return {'ok':True}
@app.post('/api/logout')
def logout(req:Request,response:Response):
    s=req.cookies.get('soc_session'); SESSIONS.discard(s); response.delete_cookie('soc_session'); return {'ok':True}
@app.get('/api/overview')
def overview(req:Request):
    require(req)
    with db() as c:
      e=c.execute("SELECT count(*) n FROM events WHERE event_time>now()-interval '24 hours'").fetchone()['n']
      h=c.execute("SELECT count(*) n FROM events WHERE event_time>now()-interval '24 hours' AND severity IN ('high','critical')").fetchone()['n']
      inv=c.execute("SELECT count(*) n FROM investigations WHERE status NOT IN ('closed','resolved')").fetchone()['n']
      cases=c.execute("SELECT count(*) n FROM soc_cases WHERE status NOT IN ('closed','resolved')").fetchone()['n']
      assets=c.execute("SELECT count(*) n FROM entities WHERE entity_type='asset'").fetchone()['n']
      inds=c.execute("SELECT count(*) n FROM entities WHERE entity_type='indicator'").fetchone()['n']
      src=c.execute("SELECT coalesce(source,'unknown') source,count(*) n FROM events GROUP BY source ORDER BY n DESC LIMIT 10").fetchall()
    return {'events_24h':e,'high_critical_24h':h,'open_investigations':inv,'open_cases':cases,'assets':assets,'indicators':inds,'sources':src}
@app.get('/api/events')
def events(req:Request,limit:int=100):
    require(req)
    with db() as c: rows=c.execute('SELECT * FROM events ORDER BY event_time DESC LIMIT %s',(min(limit,500),)).fetchall()
    return {'items':rows}
@app.get('/api/search')
def search(req:Request,q:str,limit:int=50):
    require(req); p=f'%{q}%'
    with db() as c: rows=c.execute("SELECT * FROM events WHERE data::text ILIKE %s OR coalesce(external_id,'') ILIKE %s OR coalesce(source,'') ILIKE %s ORDER BY event_time DESC LIMIT %s",(p,p,p,min(limit,200))).fetchall()
    return {'items':rows}
@app.get('/api/cases')
def cases(req:Request):
    require(req)
    with db() as c: rows=c.execute('SELECT * FROM soc_cases ORDER BY updated_at DESC LIMIT 200').fetchall()
    return {'items':rows}
@app.post('/api/cases')
def create_case(req:Request,x:CaseIn):
    require(req); iid=str(uuid.uuid4())
    with db() as c: c.execute('INSERT INTO soc_cases(id,title,priority,summary) VALUES(%s,%s,%s,%s)',(iid,x.title,x.priority,x.summary)); c.commit()
    audit(ADMIN_USER,'case.create',iid,{'title':x.title}); return {'id':iid}
@app.patch('/api/cases/{cid}')
def update_case(req:Request,cid:str,x:CaseUpdate):
    require(req)
    with db() as c:
      row=c.execute('UPDATE soc_cases SET status=coalesce(%s,status),priority=coalesce(%s,priority),summary=coalesce(%s,summary),updated_at=now() WHERE id=%s RETURNING *',(x.status,x.priority,x.summary,cid)).fetchone(); c.commit()
    if not row: raise HTTPException(404,'case not found')
    audit(ADMIN_USER,'case.update',cid,x.model_dump(exclude_none=True)); return row
@app.post('/api/cases/{cid}/events')
def attach(req:Request,cid:str,x:AttachIn):
    require(req)
    with db() as c:
      c.execute('INSERT INTO soc_case_events(case_id,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(cid,x.event_id)); c.execute('UPDATE soc_cases SET updated_at=now() WHERE id=%s',(cid,)); c.commit()
    audit(ADMIN_USER,'case.attach_event',cid,{'event_id':x.event_id}); return {'ok':True}
@app.post('/api/cases/{cid}/notes')
def note(req:Request,cid:str,x:NoteIn):
    require(req)
    with db() as c: c.execute('INSERT INTO soc_notes(case_id,author,body) VALUES(%s,%s,%s)',(cid,ADMIN_USER,x.body)); c.execute('UPDATE soc_cases SET updated_at=now() WHERE id=%s',(cid,)); c.commit()
    audit(ADMIN_USER,'case.note',cid); return {'ok':True}
@app.get('/api/cases/{cid}')
def case(req:Request,cid:str):
    require(req)
    with db() as c:
      item=c.execute('SELECT * FROM soc_cases WHERE id=%s',(cid,)).fetchone()
      ev=c.execute('SELECT e.* FROM events e JOIN soc_case_events ce ON ce.event_id=e.id WHERE ce.case_id=%s ORDER BY e.event_time DESC',(cid,)).fetchall()
      notes=c.execute('SELECT * FROM soc_notes WHERE case_id=%s ORDER BY created_at DESC',(cid,)).fetchall()
    if not item: raise HTTPException(404,'case not found')
    return {'case':item,'events':ev,'notes':notes}
@app.get('/api/graph')
def graph(req:Request,entity_type:str|None=None,external_id:str|None=None,limit:int=150):
    require(req)
    with db() as c:
      if entity_type and external_id:
        rows=c.execute('SELECT * FROM relationships WHERE (left_type=%s AND left_id=%s) OR (right_type=%s AND right_id=%s) ORDER BY last_seen DESC LIMIT %s',(entity_type,external_id,entity_type,external_id,min(limit,300))).fetchall()
      else: rows=c.execute('SELECT * FROM relationships ORDER BY last_seen DESC LIMIT %s',(min(limit,300),)).fetchall()
    nodes={}; edges=[]
    for r in rows:
      a=f"{r['left_type']}:{r['left_id']}"; b=f"{r['right_type']}:{r['right_id']}"; nodes[a]={'id':a,'label':r['left_id'],'type':r['left_type']}; nodes[b]={'id':b,'label':r['right_id'],'type':r['right_type']}; edges.append({'source':a,'target':b,'relation':r['relation'],'confidence':r['confidence']})
    return {'nodes':list(nodes.values()),'edges':edges}
@app.get('/api/audit')
def auditlog(req:Request,limit:int=100):
    require(req)
    with db() as c: return {'items':c.execute('SELECT * FROM soc_audit ORDER BY created_at DESC LIMIT %s',(min(limit,500),)).fetchall()}
@app.post('/api/ask')
async def ask(req:Request,x:AskIn):
    require(req); q=x.question; p=f'%{q}%'
    with db() as c:
      ev=c.execute("SELECT id,event_type,source,severity,event_time,external_id,data FROM events WHERE data::text ILIKE %s OR external_id ILIKE %s ORDER BY event_time DESC LIMIT 25",(p,p)).fetchall()
      ents=c.execute("SELECT entity_type,external_id,data FROM entities WHERE data::text ILIKE %s OR external_id ILIKE %s ORDER BY last_seen DESC LIMIT 25",(p,p)).fetchall()
    evidence={'events':ev,'entities':ents}
    prompt=f'''You are MARTIAN-MANHUNTER, a defensive SOC analyst. Answer only from the supplied evidence. Separate confirmed facts, hypotheses, missing evidence and safe next steps. Never claim compromise without evidence and never recommend disruptive actions without human approval. Question: {q}\nEvidence: {json.dumps(evidence,default=str)}'''
    try:
      async with httpx.AsyncClient(timeout=45) as client:
        r=await client.post(f'{OLLAMA_URL}/api/generate',json={'model':OLLAMA_MODEL,'prompt':prompt,'stream':False}); r.raise_for_status(); ans=r.json().get('response','')
    except Exception as e: ans='AI unavailable; evidence retrieved locally. '+str(e)
    audit(ADMIN_USER,'ask',details={'question':q}); return {'question':q,'evidence':evidence,'answer':ans}
@app.get('/',response_class=HTMLResponse)
def home():
 return HTMLResponse('''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Justice League SOC</title><style>body{font-family:system-ui;background:#0a0e14;color:#e9eef5;margin:0}.wrap{max-width:1400px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}.card{background:#111923;border:1px solid #253244;border-radius:12px;padding:16px}.num{font-size:30px;font-weight:700}.muted{color:#91a0b5}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #253244;text-align:left}input,button,textarea{background:#0c131c;color:#fff;border:1px solid #33445a;border-radius:8px;padding:10px}button{cursor:pointer}.row{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.critical{color:#ff7b7b}.high{color:#ffbf69}#login{max-width:380px;margin:12vh auto}.hide{display:none}.cols{display:grid;grid-template-columns:2fr 1fr;gap:14px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}}</style></head><body><div id="login" class="card"><h1>Justice League SOC</h1><p class="muted">Command Center V8</p><input id="u" placeholder="Utilisateur" value="admin"><br><br><input id="p" type="password" placeholder="Mot de passe"><br><br><button onclick="login()">Connexion</button><div id="le"></div></div><div id="app" class="wrap hide"><div class="row"><h1 style="margin-right:auto">🛡️ Justice League SOC Command Center</h1><button onclick="logout()">Déconnexion</button></div><div class="grid"><div class="card"><span class="muted">Événements 24h</span><div id="e" class="num">—</div></div><div class="card"><span class="muted">High/Critical</span><div id="h" class="num">—</div></div><div class="card"><span class="muted">Investigations</span><div id="i" class="num">—</div></div><div class="card"><span class="muted">Cases</span><div id="c" class="num">—</div></div><div class="card"><span class="muted">Assets</span><div id="a" class="num">—</div></div><div class="card"><span class="muted">Indicators</span><div id="x" class="num">—</div></div></div><div class="row"><input id="q" style="flex:1" placeholder="Rechercher IP, IOC, hostname, événement..."><button onclick="search()">Rechercher</button><input id="askq" style="flex:1" placeholder="Question à MARTIAN..."><button onclick="ask()">MARTIAN</button></div><div class="cols"><div class="card"><h2>Flux événements</h2><table><thead><tr><th>Heure</th><th>Source</th><th>Sév.</th><th>Type</th><th>ID</th></tr></thead><tbody id="rows"></tbody></table></div><div class="card"><h2>Cases</h2><button onclick="newcase()">+ Nouvelle case</button><div id="cases"></div><pre id="answer" style="white-space:pre-wrap"></pre></div></div></div><script>const $=x=>document.getElementById(x);async function j(u,o){let r=await fetch(u,o);if(r.status===401){$('login').classList.remove('hide');$('app').classList.add('hide');throw 0}return r.json()}async function login(){let r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user:$('u').value,password:$('p').value})});if(r.ok){$('login').classList.add('hide');$('app').classList.remove('hide');refresh()}else $('le').textContent='Connexion refusée'}async function logout(){await fetch('/api/logout',{method:'POST'});location.reload()}function esc(s){return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}async function refresh(){let o=await j('/api/overview');$('e').textContent=o.events_24h;$('h').textContent=o.high_critical_24h;$('i').textContent=o.open_investigations;$('c').textContent=o.open_cases;$('a').textContent=o.assets;$('x').textContent=o.indicators;load('/api/events?limit=60');let cs=await j('/api/cases');$('cases').innerHTML=cs.items.map(z=>`<p><b>${esc(z.priority)}</b> — ${esc(z.title)} <small>${esc(z.status)}</small></p>`).join('')}async function load(u){let d=await j(u);$('rows').innerHTML=d.items.map(z=>`<tr><td>${esc(z.event_time)}</td><td>${esc(z.source)}</td><td class="${z.severity==='critical'?'critical':z.severity==='high'?'high':''}">${esc(z.severity)}</td><td>${esc(z.event_type)}</td><td>${esc(z.external_id)}</td></tr>`).join('')}async function search(){let q=$('q').value.trim();if(!q)return refresh();load('/api/search?q='+encodeURIComponent(q))}async function ask(){let q=$('askq').value.trim();if(!q)return;let d=await j('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});$('answer').textContent=JSON.stringify(d.answer,null,2)}async function newcase(){let t=prompt('Titre de la case');if(!t)return;await j('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:t})});refresh()}refresh().catch(()=>{});</script></body></html>''')
