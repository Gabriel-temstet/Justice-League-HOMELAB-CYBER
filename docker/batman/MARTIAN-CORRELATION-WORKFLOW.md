# BATMAN → MARTIAN-MANHUNTER correlation workflow

Recommended n8n flow:

1. Receive Wazuh / Zeek / Suricata event.
2. Normalize into `alert`.
3. Query asset inventory → `assets`.
4. Query vulnerability/CVE store → `cves`.
5. Query ORACLE CTI store → `cti`.
6. Query historical event store → `history`.
7. POST the complete package to:
   `http://martian-core:8787/correlate`
8. If severity is `HIGH` or `CRITICAL`, send to GREEN-LANTERN.
9. Otherwise store and include in the next digest.
10. Never auto-execute remediation from the AI response.

Example payload:

```json
{
  "alert": {
    "severity": "HIGH",
    "src_ip": "10.10.20.25",
    "dst_ip": "203.0.113.10",
    "products": ["example-product"],
    "versions": ["1.2.3"],
    "indicators": ["example-domain"]
  },
  "assets": [],
  "cves": [],
  "cti": [],
  "history": [],
  "ask_ai": true
}
```
