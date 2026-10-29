# Bug Bounty Lab

## Workflow
1. Put only explicitly authorized domains/IP ranges in `config/bug-bounty/targets.json`.
2. Start with passive reconnaissance.
3. Run `bb-pipeline.sh target passive`.
4. Review the surface manually.
5. For an explicitly authorized active program, use `bb-pipeline.sh target active` and respect rate limits/exclusions.
6. Preserve evidence and redact secrets/PII.
7. Produce the report from `templates/BUG-REPORT.md`.

## Included tool families
ProjectDiscovery: subfinder, httpx, dnsx, naabu, nuclei, katana, uncover.
Recon: assetfinder, gau, hakrawler, gospider, waybackurls, anew, qsreplace.
Web: ffuf, gobuster, feroxbuster, nikto, whatweb, arjun, dalfox.
Network: nmap, masscan, dnsutils, whois, netcat.
AppSec/source: semgrep, trufflehog, detect-secrets, sqlmap, testssl.sh.
Wordlists: SecLists.

This environment is for authorized security testing only. The scope guard is a safety control, not a substitute for written authorization or program rules.
