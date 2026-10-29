
import os,subprocess,json,time
checks=[]
def sh(c):
    try:
        p=subprocess.run(c,shell=True,text=True,capture_output=True,timeout=15)
        return p.returncode==0,p.stdout[-500:],p.stderr[-500:]
    except Exception as e:return False,"",str(e)
for name,cmd in [
    ("docker","docker info"),
    ("compose","docker compose version"),
]:
    ok,out,err=sh(cmd); checks.append({"name":name,"ok":ok,"detail":out or err})
print(json.dumps({"ok":all(x["ok"] for x in checks),"checks":checks},indent=2))
