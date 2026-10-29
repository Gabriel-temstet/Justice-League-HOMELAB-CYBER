# V9 — Justice League Bug Bounty Lab

## Mission
A dedicated, isolated container for authorized bug-bounty/AppSec work. It is not a general-purpose attack box.

## Included tool families
- Recon: subfinder, assetfinder, dnsx, httpx, naabu, nmap, masscan
- Crawling/content: katana, ffuf, gobuster, feroxbuster, waybackurls
- Web assessment: nikto, whatweb, sqlmap, arjun, nuclei
- Parameter/URL helpers: qsreplace, uro, anew
- TLS: testssl
- Source/AppSec: semgrep, trufflehog, detect-secrets
- Wordlists: SecLists
- Python helpers: requests, BeautifulSoup, dnspython

Tool versions are resolved during image build; check with `bb-run TOOL --help` and pin image digests for long-term reproducibility.

## Mandatory authorization boundary
`/scope/targets.json` contains the explicit allow-list. `bb-run` refuses targets outside it. Replace the example values only with assets you are contractually authorized to test.

The runner is deliberately not a stealth/evasion framework and does not automate credential attacks, persistence, destructive exploitation, or out-of-scope scanning.

## Start
```bash
cp config/bug-bounty/targets.example.json config/bug-bounty/targets.json
nano config/bug-bounty/targets.json
./scripts/deploy-v9.sh
./scripts/bug-bounty-shell.sh
```

Inside the container:
```bash
bb-run subfinder -d your-authorized-domain.tld -silent
bb-run httpx -l /workspace/subdomains.txt -silent
bb-run nuclei -l /workspace/urls.txt -severity low,medium,high,critical -safe
```

For tools that need files rather than a single target, place the input under `/workspace` and ensure every target in the input is covered by the allow-list before execution.

## Important
The allow-list is a safety gate, not proof of authorization. You remain responsible for the bug-bounty program rules, rate limits, exclusions, and legal authorization. Use the program's exact scope and testing policy.
