FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends nmap ca-certificates curl python3 python3-psutil python3-scapy && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY scanner.sh start.sh run_audits.py tool_cli.py ./
COPY tools/audit_ports_localmachine.py tools/audit_reseau_machine_distante.py tools/
RUN mkdir -p /results
CMD ["/bin/bash","start.sh"]
