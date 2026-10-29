import os,httpx
from fastapi import FastAPI,Header,HTTPException
from normalizer import normalize
app=FastAPI(title="BATMAN V6",version="6.0.0")
MARTIAN=os.getenv("MARTIAN_URL","http://martian-core:8787"); TOKEN=os.getenv("AI_GATEWAY_TOKEN","")
def auth(t):
    if TOKEN and t!=TOKEN: raise HTTPException(status_code=401,detail="invalid token")
@app.get("/health")
def health(): return {"status":"ok","service":"BATMAN","version":"6.0.0"}
@app.post("/normalize")
async def norm(payload:dict,source:str|None=None,forward:bool=True,x_ai_gateway_token:str|None=Header(default=None)):
    auth(x_ai_gateway_token); ev=normalize(payload,source)
    if not forward:return ev
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.post(f"{MARTIAN}/ingest",json=ev,headers={"x-ai-gateway-token":TOKEN} if TOKEN else {})
        r.raise_for_status()
        return {"normalized":ev,"martian":r.json()}
