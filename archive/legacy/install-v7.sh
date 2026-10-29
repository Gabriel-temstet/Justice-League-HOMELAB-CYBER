#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$ROOT/config/config.env"
[[ -f "$CFG" ]] || { echo "Missing $CFG"; exit 1; }
source "$CFG"

log(){ printf '\n\033[1;36m[JUSTICE LEAGUE]\033[0m %s\n' "$*"; }
die(){ echo "ERROR: $*" >&2; exit 1; }
require_root(){ [[ $EUID -eq 0 ]] || die "Run as root."; }

check(){
  require_root
  log "Checking host"
  command -v awk >/dev/null
  command -v grep >/dev/null
  command -v curl >/dev/null
  command -v git >/dev/null || true
  echo "CPU: $(nproc)"
  echo "RAM: $(awk '/MemTotal/ {printf "%.0f GB\n",$2/1024/1024}' /proc/meminfo)"
  echo "Disks:"
  lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | head -40
  echo "Network:"
  ip -br link
  echo "Virtualization:"
  grep -Eoc '(vmx|svm)' /proc/cpuinfo || true
  echo "Kernel: $(uname -r)"
  echo "WARNING: install phase may alter bootloader/kernel/network and requires a fresh Debian host."
}

secrets(){
  require_root
  mkdir -p "$ROOT/config"
  python3 - "$CFG" <<'PY'
import secrets, sys
p=sys.argv[1]
s=open(p).read()
vals={
"POSTGRES_PASSWORD":secrets.token_urlsafe(32),
"REDIS_PASSWORD":secrets.token_urlsafe(32),
"AI_GATEWAY_TOKEN":secrets.token_urlsafe(32),
"BATMAN_DB_PASSWORD":secrets.token_urlsafe(32),
}
lines=s.splitlines()
for k,v in vals.items():
    lines.append(f"{k}={v}")
open(p,"w").write("\n".join(lines)+"\n")
PY
  chmod 600 "$CFG"
  log "Secrets generated in $CFG"
}

install_pve(){
  require_root
  [[ "$CONFIRM_INSTALL" == "INSTALL" ]] || die "Set CONFIRM_INSTALL=INSTALL in config/config.env first."
  log "Installing Proxmox prerequisites"
  apt-get update
  apt-get install -y curl gnupg ca-certificates git sudo ifupdown2 chrony
  if ! grep -q 'proxmox.com/debian/pve' /etc/apt/sources.list.d/pve-install-repo.list 2>/dev/null; then
    echo "deb http://download.proxmox.com/debian/pve trixie pve-no-subscription" >/etc/apt/sources.list.d/pve-install-repo.list
  fi
  curl -fsSL https://enterprise.proxmox.com/debian/proxmox-release-trixie.gpg -o /etc/apt/trusted.gpg.d/proxmox-release-trixie.gpg
  apt-get update
  apt-get install -y proxmox-default-kernel proxmox-ve postfix open-iscsi
  hostnamectl set-hostname "$HOSTNAME"
  log "Proxmox installed. Reboot is required."
}

post_reboot(){
  require_root
  sysctl -w vm.max_map_count=262144
  cat >/etc/sysctl.d/99-justice-league.conf <<EOF
vm.max_map_count=262144
fs.inotify.max_user_instances=8192
EOF
  sysctl --system >/dev/null
  mkdir -p "$DATA_ROOT" "$BACKUP_ROOT"
  chmod 750 "$DATA_ROOT" "$BACKUP_ROOT"
  log "Post-reboot host configuration complete."
}

deploy(){
  require_root
  log "Deploying Justice League control plane"
  mkdir -p "$DATA_ROOT"/{batman,oracle,martian,green-lantern,monitoring}
  cp -a "$ROOT/docker/." "$DATA_ROOT/"
  cp "$CFG" "$DATA_ROOT/config.env"
  chmod 600 "$DATA_ROOT/config.env"
  (cd "$DATA_ROOT/batman" && docker compose up -d) 2>/dev/null || true
  (cd "$DATA_ROOT/oracle" && docker compose up -d) 2>/dev/null || true
  (cd "$DATA_ROOT/martian" && docker compose up -d) 2>/dev/null || true
  (cd "$DATA_ROOT/green-lantern" && docker compose up -d) 2>/dev/null || true
  (cd "$DATA_ROOT/monitoring" && docker compose up -d) 2>/dev/null || true
  log "Control-plane containers requested. Check scripts/healthcheck.sh."
}

case "${1:-}" in
  check) check ;;
  secrets) secrets ;;
  install|install-pve) install_pve ;;
  post-reboot) post_reboot ;;
  deploy) deploy ;;
  *) echo "Usage: $0 {check|secrets|install|post-reboot|deploy}" ; exit 2 ;;
esac
