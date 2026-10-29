from datetime import datetime,timezone
def g(d,*keys):
    for k in keys:
        if d.get(k) not in (None,""): return d[k]
def normalize(p,source=None):
    src=source or g(p,"source","vendor","observer") or "unknown"
    ts=g(p,"timestamp","ts","time","@timestamp")
    if isinstance(ts,(int,float)): ts=datetime.fromtimestamp(ts,tz=timezone.utc).isoformat()
    else: ts=ts or datetime.now(timezone.utc).isoformat()
    sip=g(p,"src_ip","source_ip","id.orig_h","srcip")
    dip=g(p,"dst_ip","destination_ip","id.resp_h","dest_ip","dstip")
    sig=g(p,"signature","rule","alert","notice","msg")
    sev=g(p,"severity","level","rule_level") or "info"
    typ=g(p,"event_type","type") or "security_event"
    eid=g(p,"id","flow_id","alert_id")
    inds=[x for x in [sip,dip,g(p,"domain","query","host"),g(p,"url"),g(p,"sha256","md5","hash")] if x]
    return {"source":src,"event_type":typ,"severity":str(sev),"timestamp":ts,
            "external_id":str(eid) if eid else None,"asset_ids":[],"indicators":list(dict.fromkeys(map(str,inds))),
            "data":{"src_ip":sip,"dst_ip":dip,"signature":sig,"raw":p}}
