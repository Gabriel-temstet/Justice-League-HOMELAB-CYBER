import json, hashlib
from datetime import datetime, timezone
from typing import Any

SEVERITY_WEIGHT = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

def norm(v):
    return str(v or "").strip().lower()

def event_id(event: dict[str, Any]) -> str:
    raw = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def correlate(alert: dict, assets: list, cves: list, cti: list, history: list) -> dict:
    alert_text = norm(json.dumps(alert))
    src_ip = norm(alert.get("src_ip") or alert.get("source_ip"))
    dst_ip = norm(alert.get("dst_ip") or alert.get("destination_ip"))
    asset_hits = []
    for a in assets:
        hay = norm(json.dumps(a))
        ips = [norm(a.get(k)) for k in ("ip","ip_address","address")]
        if any(x and x in {src_ip, dst_ip} for x in ips) or (hay and any(x in hay for x in (src_ip,dst_ip) if x)):
            asset_hits.append(a)

    cve_hits = []
    alert_products = {norm(x) for x in alert.get("products", [])}
    alert_versions = {norm(x) for x in alert.get("versions", [])}
    for c in cves:
        hay = norm(json.dumps(c))
        cve_id = norm(c.get("cve") or c.get("id"))
        if cve_id and cve_id in alert_text:
            cve_hits.append(c)
        elif any(p and p in hay for p in alert_products):
            cve_hits.append(c)
        elif any(v and v in hay for v in alert_versions):
            cve_hits.append(c)

    cti_hits = []
    indicators = {norm(x) for x in alert.get("indicators", [])}
    for item in cti:
        hay = norm(json.dumps(item))
        if any(i and i in hay for i in indicators):
            cti_hits.append(item)

    related_history = []
    for h in history:
        htext = norm(json.dumps(h))
        if (src_ip and src_ip in htext) or (dst_ip and dst_ip in htext):
            related_history.append(h)

    score = SEVERITY_WEIGHT.get(str(alert.get("severity","INFO")).upper(), 0)
    if asset_hits: score += 1
    if cve_hits: score += 2
    if cti_hits: score += 2
    if related_history: score += 1

    level = "INFO"
    if score >= 7: level = "CRITICAL"
    elif score >= 5: level = "HIGH"
    elif score >= 3: level = "MEDIUM"
    elif score >= 1: level = "LOW"

    return {
        "correlation_id": event_id(alert),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": level,
        "score": score,
        "asset_matches": asset_hits,
        "cve_matches": cve_hits,
        "cti_matches": cti_hits,
        "historical_matches": related_history[-50:],
        "evidence_counts": {
            "assets": len(asset_hits),
            "cves": len(cve_hits),
            "cti": len(cti_hits),
            "history": len(related_history)
        },
        "requires_human_review": level in {"HIGH","CRITICAL"}
    }
