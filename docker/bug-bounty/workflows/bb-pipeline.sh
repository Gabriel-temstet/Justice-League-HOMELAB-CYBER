#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
MODE="${2:-passive}"
PROFILE="${3:-authorized}"
[[ -n "$TARGET" ]] || { echo "Usage: bb-pipeline.sh target [passive|active] [authorized|lab]"; exit 2; }
[[ "$MODE" == passive || "$MODE" == active ]] || { echo "Invalid mode"; exit 2; }
[[ "$PROFILE" == authorized || "$PROFILE" == lab ]] || { echo "Invalid profile"; exit 2; }
GUARD_ARGS=()
[[ "$PROFILE" == lab ]] && GUARD_ARGS+=(--lab)
${BASH_SOURCE[0]%/*}/../bb-run --help >/dev/null 2>&1 || true
if [[ "$PROFILE" == lab ]]; then scope-guard --lab "$TARGET"; else scope-guard "$TARGET"; fi
SAFE="/results/$(echo "$TARGET" | tr '/:' '__')"
mkdir -p "$SAFE"
BB_PREFIX=()
[[ "$PROFILE" == lab ]] && BB_PREFIX+=(--lab)
runbb(){ bb-run "${BB_PREFIX[@]}" "$@"; }
echo "[1/7] subdomains"; runbb subfinder -d "$TARGET" -silent -o "$SAFE/subdomains.txt" || true
echo "[2/7] DNS"; if [[ -s "$SAFE/subdomains.txt" ]]; then runbb dnsx -l "$SAFE/subdomains.txt" -silent -resp -o "$SAFE/dns.txt" || true; fi
echo "[3/7] HTTP surface"; if [[ -s "$SAFE/subdomains.txt" ]]; then runbb httpx -l "$SAFE/subdomains.txt" -silent -follow-redirects -status-code -title -tech-detect -o "$SAFE/http.txt" || true; fi
echo "[4/7] crawl"; if [[ -s "$SAFE/http.txt" ]]; then awk '{print $1}' "$SAFE/http.txt" | while read -r u; do scope-guard "${GUARD_ARGS[@]}" "$u" >/dev/null && katana -u "$u" -silent -jc -o "$SAFE/katana.txt" || true; done; fi
if command -v gau >/dev/null 2>&1; then echo "[5/7] passive URL history"; gau --subs "$TARGET" 2>/dev/null | sort -u > "$SAFE/gau.txt" || true; else : > "$SAFE/gau.txt"; fi
if [[ "$MODE" == active ]]; then
  echo "[6/7] nuclei safe active templates"; if [[ -s "$SAFE/http.txt" ]]; then awk '{print $1}' "$SAFE/http.txt" | while read -r u; do scope-guard "${GUARD_ARGS[@]}" "$u" >/dev/null && nuclei -silent -safe -severity low,medium,high,critical -u "$u" -o "$SAFE/nuclei.txt" || true; done; fi
  if command -v dalfox >/dev/null 2>&1 && [[ -s "$SAFE/gau.txt" ]]; then echo "[7/7] XSS triage"; dalfox file "$SAFE/gau.txt" --silence --output "$SAFE/dalfox.txt" || true; fi
else echo "[6/7] passive mode: active scanners skipped"; echo "[7/7] passive mode: no active validation"; fi
printf '\nResults: %s\nProfile: %s\n' "$SAFE" "$PROFILE"
