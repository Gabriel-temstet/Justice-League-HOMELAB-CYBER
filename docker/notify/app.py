import os,httpx
from fastapi import FastAPI
from pydantic import BaseModel
app=FastAPI(title='GREEN LANTERN V8')
DISCORD=os.getenv('DISCORD_WEBHOOK_URL',''); DRY=os.getenv('NOTIFY_DRY_RUN','YES').upper()=='YES'; WA_TOKEN=os.getenv('WHATSAPP_ACCESS_TOKEN',''); WA_PHONE=os.getenv('WHATSAPP_PHONE_NUMBER_ID',''); WA_TO=os.getenv('WHATSAPP_TO','')
class Msg(BaseModel): title:str='Justice League SOC'; body:str; severity:str='info'
@app.get('/health')
def health(): return {'status':'ok','discord':bool(DISCORD),'whatsapp':bool(WA_TOKEN and WA_PHONE and WA_TO),'dry_run':DRY}
@app.post('/notify')
async def notify(m:Msg):
 if DRY:return {'status':'dry_run','message':m.model_dump()}
 out={}
 async with httpx.AsyncClient(timeout=15) as c:
  if DISCORD:
   r=await c.post(DISCORD,json={'content':f'**{m.title}**\n[{m.severity.upper()}] {m.body}'}); out['discord']=r.status_code
  if WA_TOKEN and WA_PHONE and WA_TO:
   url=f'https://graph.facebook.com/v22.0/{WA_PHONE}/messages'; r=await c.post(url,headers={'Authorization':f'Bearer {WA_TOKEN}'},json={'messaging_product':'whatsapp','to':WA_TO,'type':'text','text':{'body':f'{m.title}\n[{m.severity.upper()}] {m.body}'}}); out['whatsapp']=r.status_code
 return {'status':'sent','channels':out}
