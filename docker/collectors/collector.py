import os,json,time,hashlib,datetime,httpx
MARTIAN=os.getenv('MARTIAN_URL','http://martian-core:8787'); TOKEN=os.getenv('AI_GATEWAY_TOKEN',''); INTERVAL=float(os.getenv('COLLECTOR_INTERVAL','5'))
SOURCES={'SURICATA_EVE_PATH':'suricata','ZEEK_CONN_PATH':'zeek','WAZUH_ALERTS_PATH':'wazuh'}
positions={}
def post(obj):
 try:
  r=httpx.post(MARTIAN+'/ingest',headers={'X-AI-Gateway-Token':TOKEN},json=obj,timeout=10); r.raise_for_status()
  if obj.get('severity') in ('high','critical'):
   title=f"{obj.get('severity','').upper()} — {obj.get('event_type','security')} — {obj.get('external_id','')}"
   try:
    httpx.post(MARTIAN+'/investigations',headers={'X-AI-Gateway-Token':TOKEN},json={'title':title,'query':json.dumps(obj.get('data',{}),default=str),'priority':obj.get('severity','medium')},timeout=10)
   except Exception as e: print('investigation:',e,flush=True)
   try:
    httpx.post(os.getenv('GREEN_LANTERN_URL','http://green-lantern:8898')+'/notify',json={'title':'Justice League SOC','body':title,'severity':obj.get('severity','info')},timeout=10)
   except Exception as e: print('notify:',e,flush=True)
 except Exception as e: print('ingest:',e,flush=True)
def normalize(src,row):
 s=str(row.get('severity') or row.get('level') or row.get('event_type') or 'info').lower(); sev='critical' if s in ('critical','crit') else 'high' if s in ('high','error','err') else 'medium' if s in ('medium','warning','warn') else 'low' if s=='low' else 'info'
 indicators=[]
 for k in ('src_ip','dest_ip','dst_ip','source_ip','destination_ip','domain','hostname','url','sha256','md5'):
  if row.get(k): indicators.append(str(row[k]))
 ts=row.get('timestamp') or row.get('@timestamp') or row.get('event_time')
 ext=row.get('id') or row.get('event_id') or row.get('uid')
 if not ext: ext=hashlib.sha256(json.dumps(row,sort_keys=True,default=str).encode()).hexdigest()[:24]
 return {'source':src,'event_type':str(row.get('event_type') or row.get('type') or 'security'),'severity':sev,'timestamp':ts,'external_id':f'{src}:{ext}','asset_ids':[], 'indicators':indicators,'data':row}
def tail(path,src):
 if not path or not os.path.exists(path): return
 pos=positions.get(path,0)
 try:
  size=os.path.getsize(path)
  if size<pos: pos=0
  with open(path,'r',errors='ignore') as f:
   f.seek(pos)
   for line in f:
    try: row=json.loads(line); post(normalize(src,row))
    except Exception: pass
   positions[path]=f.tell()
 except Exception as e: print('tail',path,e,flush=True)
while True:
 for env,src in SOURCES.items(): tail(os.getenv(env,''),src)
 time.sleep(INTERVAL)
