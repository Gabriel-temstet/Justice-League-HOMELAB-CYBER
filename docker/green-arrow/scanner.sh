#!/bin/bash
set -u
CIDRS="${AUTHORIZED_CIDRS:-}"
INTERVAL="${DISCOVERY_INTERVAL:-3600}"
while true; do
  if [[ -n "$CIDRS" ]]; then
    for cidr in $CIDRS; do
      nmap -sn -n "$cidr" -oG - 2>/dev/null | awk '/Up$/{print $2}' | while read -r ip; do
        curl -fsS -X POST "$MARTIAN_URL/memory/entity" -H 'Content-Type: application/json' -H "X-AI-Gateway-Token: $AI_GATEWAY_TOKEN" -d "{\"entity_type\":\"asset\",\"external_id\":\"$ip\",\"data\":{\"ip\":\"$ip\",\"source\":\"GREEN-ARROW\"}}" >/dev/null || true
      done
    done
  fi
  sleep "$INTERVAL"
done
