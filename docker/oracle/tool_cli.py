#!/usr/bin/env python3
"""CLI non interactive appelee par la console web : remove DOMAIN (l'ajout et le passage utilisent osint_veille.py)."""
import os, sys, re
from pathlib import Path
f = Path(os.getenv("HOME", "/data/home")) / "veille-osint" / "domaines.txt"
if len(sys.argv) == 3 and sys.argv[1] == "remove" and re.fullmatch(r"[a-z0-9.-]{3,253}", sys.argv[2]):
    cur = f.read_text().splitlines() if f.exists() else []
    new = [l for l in cur if l.strip().lower() != sys.argv[2]]
    f.write_text("\n".join(new) + ("\n" if new else ""))
    print("retire:" if len(new) != len(cur) else "absent:", sys.argv[2])
else:
    print("usage: tool_cli.py remove DOMAIN"); sys.exit(2)
