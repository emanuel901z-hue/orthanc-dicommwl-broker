#!/bin/bash
# Provision the Ubuntu WSL distro for the mwl-broker stack.
#
# Runs as root *inside* the distro (called by deploy/windows/bootstrap.ps1).
# Idempotent: every step checks first and does nothing when it is already done.
#
#   MWL_DISTRO_USER   the WSL user that runs docker (default: admin)
#   MWL_DOCKER_STORE  image store: overlay2 (default) or containerd

set -euo pipefail

DISTRO_USER="${MWL_DISTRO_USER:-admin}"
DOCKER_STORE="${MWL_DOCKER_STORE:-overlay2}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[1;33m!\033[0m %s\n' "$*"; }

# ── 1. Docker Engine + Compose ───────────────────────────────────────────────
if command -v docker >/dev/null 2>&1; then
  ok "Docker ist bereits installiert ($(docker --version | awk '{print $3}' | tr -d ,))"
else
  step "Docker Engine installieren"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg >/dev/null
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
  ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) installiert"
fi

# ── 2. klassischer Image-Store ───────────────────────────────────────────────
# Docker 29 defaults to the containerd snapshotter, where BuildKit fails with
# "failed to Lchown ... libaom.so" on this image set. The classic overlay2 store
# is what the stack is built and tested on.
current_store() {
  python3 - <<'PY' 2>/dev/null || echo unknown
import json
try:
    d = json.load(open("/etc/docker/daemon.json"))
except Exception:
    print("unset"); raise SystemExit
f = d.get("features", {})
print("classic" if f.get("containerd-snapshotter") is False else "containerd")
PY
}

if [ "$DOCKER_STORE" = "overlay2" ]; then
  store="$(current_store)"
  if [ "$store" = "classic" ]; then
    ok "klassischer overlay2-Store ist bereits aktiv"
  elif [ -n "$(docker ps -aq 2>/dev/null)" ]; then
    warn "Docker nutzt den '$store'-Store und es laufen Container — Store bleibt unverändert"
    warn "Umstellen erst nach 'docker compose down' (die Images müssen danach neu geladen werden)"
  else
    step "Docker auf den klassischen overlay2-Store umstellen"
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "storage-driver": "overlay2",
  "features": { "containerd-snapshotter": false }
}
JSON
    systemctl restart docker
    ok "daemon.json geschrieben, Docker neu gestartet"
  fi
fi

# ── 3. 127.0.0.1-Hang im Mirrored-Mode ───────────────────────────────────────
# In mirrored networking the RST for a closed port on 127.0.0.1 arrives with a
# corrupted destination port (microsoft/WSL#10855); the connect then hangs for
# ~130 s instead of failing. That makes every "is it up?" probe unreliable —
# setup.sh --check hangs on a stopped stack because of it. Flushing the mirrored
# route puts 127.0.0.1 back on the kernel's local table.
UNIT=/etc/systemd/system/wsl-127-route-fix.service
if [ -f "$UNIT" ]; then
  ok "127.0.0.1-Workaround ist bereits eingerichtet"
else
  step "Workaround für den 127.0.0.1-Hang einrichten (microsoft/WSL#10855)"
  cat > "$UNIT" <<'UNITFILE'
[Unit]
Description=WSL mirrored-mode workaround: keep 127.0.0.1 on the local route table (microsoft/WSL#10855)
After=network.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c "for i in $(seq 1 60); do ip route flush table 127 2>/dev/null || true; sleep 1; done"

[Install]
WantedBy=multi-user.target
UNITFILE
  systemctl daemon-reload
  systemctl enable --now wsl-127-route-fix.service >/dev/null 2>&1 || true
  ok "wsl-127-route-fix.service aktiviert"
fi

# ── 4. Dienst und Gruppenmitgliedschaft ──────────────────────────────────────
systemctl enable --now docker >/dev/null 2>&1 || true
if [ "$(systemctl is-active docker)" != "active" ]; then
  warn "docker.service ist nicht aktiv — 'systemctl status docker' prüfen"
else
  ok "docker.service läuft"
fi

if id "$DISTRO_USER" >/dev/null 2>&1; then
  if id -nG "$DISTRO_USER" | tr ' ' '\n' | grep -qx docker; then
    ok "$DISTRO_USER ist bereits in der docker-Gruppe"
  else
    usermod -aG docker "$DISTRO_USER"
    ok "$DISTRO_USER zur docker-Gruppe hinzugefügt"
  fi
else
  warn "Benutzer '$DISTRO_USER' existiert nicht — Gruppenmitgliedschaft übersprungen"
fi

printf '\n'
ok "WSL-Provisionierung abgeschlossen"
