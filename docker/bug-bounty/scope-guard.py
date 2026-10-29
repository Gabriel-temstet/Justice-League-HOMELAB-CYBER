#!/usr/bin/env python3
import argparse, ipaddress, json, socket, sys
from urllib.parse import urlparse

LAB_NETS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]

def host_from_target(t):
    if '://' not in t: t='http://'+t
    return urlparse(t).hostname

def lab_host(host):
    if not host: return False
    h=host.lower().rstrip('.')
    if h in {'localhost'} or h.endswith(('.local','.test','.internal','.home','.lan')):
        return True
    try:
        ip=ipaddress.ip_address(h)
        return any(ip in n for n in LAB_NETS)
    except ValueError:
        try:
            infos=socket.getaddrinfo(h, None)
            return any(any(ipaddress.ip_address(x[4][0]) in n for n in LAB_NETS) for x in infos)
        except Exception:
            return False

def allowed(host, scopes):
    try:
        ip=ipaddress.ip_address(host)
        for s in scopes:
            try:
                if ip in ipaddress.ip_network(s, strict=False): return True
            except ValueError: pass
    except ValueError: pass
    h=host.lower().rstrip('.')
    for s in scopes:
        s=s.lower().lstrip('*.').rstrip('.')
        if h==s or h.endswith('.'+s): return True
    return False

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scope', default='/scope/targets.json')
    p.add_argument('--lab', action='store_true', help='Allow lab/private targets without requiring them in targets.json')
    p.add_argument('targets', nargs='+')
    a=p.parse_args()
    try: data=json.load(open(a.scope))
    except Exception as e:
        data={'allow': [], 'exclude': []}
        if not a.lab:
            print(f'SCOPE ERROR: {e}', file=sys.stderr); return 2
    scopes=data.get('allow',[])
    excludes=data.get('exclude',[])
    bad=[]
    for t in a.targets:
        h=host_from_target(t)
        if not h:
            bad.append(t); continue
        if allowed(h, excludes):
            bad.append(t); continue
        if a.lab:
            if not lab_host(h): bad.append(t)
        elif not scopes or not allowed(h,scopes):
            bad.append(t)
    if bad:
        print('BLOCKED: target is outside the active scope/mode:', file=sys.stderr)
        for t in bad: print('  '+t, file=sys.stderr)
        return 3
    print('SCOPE_OK')
    return 0
if __name__=='__main__': sys.exit(main())
