import os,httpx
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
app=FastAPI(title="GREEN LANTERN V6",version="6.0.0")
WEBHOOK=os.getenv("DISCORD_WEBHOOK_URL",""); TOKEN=os.getenv("AI_GATEWAY_TOKEN","")
DRY=os.getenv("NOTIFY_DRY_RUN","YES").upper()!="NO"
class Notification(BaseModel):
    title:str; severity:str="info"; message:str; evidence:dict={}
def auth(t):
    if TOKEN and t!=TOKEN: raise HTTPException(status_code=401,detail="invalid token")
@app.get("/health")
def health(): return {"status":"ok","service":"GREEN-LANTERN","dry_run":DRY}
@app.post("/notify")
async def notify(n:Notification,x_ai_gateway_token:str|None=Header(default=None)):
    auth(x_ai_gateway_token)
    payload={"content":f"[{n.severity.upper()}] {n.title}\n{n.message}"}
    if DRY or not WEBHOOK:return {"sent":False,"dry_run":True,"payload":payload}
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.post(WEBHOOK,json=payload); r.raise_for_status()
    return {"sent":True,"channel":"discord"}
