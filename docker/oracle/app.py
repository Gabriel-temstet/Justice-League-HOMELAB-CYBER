import os,time,hashlib,sqlite3,json,feedparser,httpx
DB='/data/oracle.db'; FEEDS=[x for x in os.getenv('CTI_FEEDS','').split(';') if x]; MARTIAN=os.getenv('MARTIAN_URL','http://martian-core:8787'); TOKEN=os.getenv('AI_GATEWAY_TOKEN',''); INTERVAL=int(os.getenv('CTI_INTERVAL','900'))
db=sqlite3.connect(DB); db.execute('create table if not exists items(id text primary key,title text,link text,published text,summary text,source text)'); db.commit()
while True:
  for url in FEEDS:
    try:
      f=feedparser.parse(url)
      for e in f.entries[:50]:
        link=e.get('link',''); title=e.get('title',''); iid=hashlib.sha256((link or title).encode()).hexdigest()
        before=db.execute('select 1 from items where id=?',(iid,)).fetchone()
        db.execute('insert or ignore into items values(?,?,?,?,?,?)',(iid,title,link,e.get('published',''),e.get('summary','')[:4000],url)); db.commit()
        if not before:
          item={'id':iid,'title':title,'link':link,'published':e.get('published',''),'summary':e.get('summary','')[:4000],'source':url}
          try:
            httpx.post(MARTIAN+'/memory/entity',headers={'X-AI-Gateway-Token':TOKEN},json={'entity_type':'cti','external_id':iid,'data':item},timeout=10)
          except Exception as ex: print('martian cti error',ex,flush=True)
    except Exception as ex: print('feed error',url,ex,flush=True)
  time.sleep(INTERVAL)
