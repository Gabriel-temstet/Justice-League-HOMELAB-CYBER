FROM debian:13-slim
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive TZ=Europe/Paris
# Multi-architecture (amd64 / arm64 : Mac Apple Silicon) : les paquets de base sont obligatoires,
# les outils optionnels sont installes un par un et ignores s'ils n'existent pas pour l'architecture.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git jq unzip zip python3 python3-pip python3-venv \
    golang-go build-essential dnsutils whois netcat-openbsd nmap libpcap-dev libssl-dev && \
    for p in masscan nikto sqlmap whatweb ffuf gobuster feroxbuster hydra testssl.sh; do \
      apt-get install -y --no-install-recommends "$p" || echo "[bug-bounty] paquet $p indisponible sur $(dpkg --print-architecture), ignore"; \
    done && rm -rf /var/lib/apt/lists/*
ENV GOPATH=/opt/go GOBIN=/usr/local/bin
RUN mkdir -p /opt/go
# ProjectDiscovery / reconnaissance stack
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest && \
    go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest && \
    go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install github.com/projectdiscovery/katana/cmd/katana@latest && \
    go install github.com/tomnomnom/assetfinder@latest && \
    go install github.com/tomnomnom/anew@latest && \
    go install github.com/tomnomnom/waybackurls@latest && \
    go install github.com/tomnomnom/qsreplace@latest && \
    go install github.com/lc/gau/v2/cmd/gau@latest && \
    go install github.com/hakluke/hakrawler@latest && \
    go install github.com/jaeles-project/gospider@latest && \
    go install github.com/projectdiscovery/uncover/cmd/uncover@latest
# AppSec / source analysis
RUN pip3 install --break-system-packages --no-cache-dir \
    arjun uro semgrep trufflehog detect-secrets dnspython requests beautifulsoup4 pyjwt
# Additional static binaries
RUN curl -fsSL https://api.github.com/repos/danielmiessler/SecLists/releases/latest | jq -r '.assets[] | select(.name|endswith("zip")) | .browser_download_url' | head -1 | xargs -r curl -fL -o /tmp/seclists.zip && \
    mkdir -p /opt/wordlists && unzip -q /tmp/seclists.zip -d /opt/wordlists || true; rm -f /tmp/seclists.zip
COPY scope-guard.py /usr/local/bin/scope-guard
COPY bb-run /usr/local/bin/bb-run
COPY workflows/bb-pipeline.sh /usr/local/bin/bb-pipeline.sh
COPY templates /opt/templates
RUN chmod +x /usr/local/bin/scope-guard /usr/local/bin/bb-run /usr/local/bin/bb-pipeline.sh
RUN mkdir -p /workspace /scope /results /root/.config/nuclei && nuclei -update-templates -silent || true
WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]

# Web triage / XSS helper
RUN git clone --depth 1 https://github.com/hahwul/dalfox.git /opt/dalfox && cd /opt/dalfox && go build -o /usr/local/bin/dalfox . || true
