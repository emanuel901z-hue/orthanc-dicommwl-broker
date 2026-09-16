#!/usr/bin/env bash
# bootstrap.sh — plug-and-play setup for the mwl-broker stack on Ubuntu Server.
#
#   ./bootstrap.sh            base stack (orthanc + postgres + broker + OE3)
#   ./bootstrap.sh --demo     additionally starts mock RIS sources + peer PACS
#   ./bootstrap.sh --check    only run preflight checks, don't start anything
#
# Idempotent: safe to re-run (docker compose up -d is a no-op when up-to-date).
set -euo pipefail
cd "$(dirname "$0")"

DEMO=0
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --demo) DEMO=1 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) grep '^#' "$0" | head -8; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33mWARN:\033[0m %s\n' "$*" >&2; }
fail()  { printf '\033[1;31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

# ── 1. Docker ────────────────────────────────────────────────────────────────
info "Checking Docker…"
if ! command -v docker >/dev/null 2>&1; then
  info "Docker not found — installing via get.docker.com"
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || fail "docker compose plugin missing — install docker-compose-plugin"

if ! docker info >/dev/null 2>&1; then
  if id -nG | grep -qw docker; then
    fail "Docker daemon not reachable — log out/in (group 'docker' just added) or run: newgrp docker"
  fi
  warn "Adding $USER to docker group — re-run this script after re-login"
  sudo usermod -aG docker "$USER"
  fail "Group membership required. Run: newgrp docker && $0"
fi

# ── 2. .env ──────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  info "Creating .env from .env.example"
  cp .env.example .env
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a

# ── 3. Port collision check (host runs other docker projects) ────────────────
info "Checking for occupied ports…"
PORTS=( "${OE3_PORT:-8082}" "${BROKER_DICOM_PORT:-11113}" "${ORTHANC_DICOM_PORT:-4242}"
        "${ORTHANC_HTTP_PORT:-8042}" "${BROKER_API_PORT:-8081}" )
[ "$DEMO" = 1 ] && PORTS+=( "${MOCK_RIS_A_PORT:-11114}" "${MOCK_RIS_B_PORT:-11115}" "${PEER_HTTP_PORT:-8043}" "${PEER_DICOM_PORT:-4243}" )
collision=0
for p in "${PORTS[@]}"; do
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${p}$"; then
    warn "port $p is already in use — adjust it in .env"
    collision=1
  fi
done
[ "$collision" = 1 ] && warn "Port collisions detected — continuing anyway (compose will fail on the occupied port)"

[ "$CHECK_ONLY" = 1 ] && { info "Preflight done."; exit 0; }

# ── 4. Start stack ───────────────────────────────────────────────────────────
COMPOSE_FILES=(-f docker-compose.yml)
[ "$DEMO" = 1 ] && COMPOSE_FILES+=(-f docker-compose.demo.yml)

info "Building + starting stack…"
docker compose "${COMPOSE_FILES[@]}" up -d --build --remove-orphans

# ── 5. Wait for health ───────────────────────────────────────────────────────
info "Waiting for services to become healthy…"
deadline=$((SECONDS + 180))
wait_http() {
  local name="$1" url="$2"
  until curl -sf "$url" >/dev/null 2>&1; do
    [ $SECONDS -gt $deadline ] && { fail "$name did not become healthy — check: docker compose logs $3"; }
    sleep 2
  done
  info "$name OK"
}
wait_http "orthanc"  "http://127.0.0.1:${ORTHANC_HTTP_PORT:-8042}/system" orthanc
wait_http "broker"   "http://127.0.0.1:${BROKER_API_PORT:-8081}/healthz" mwl-broker
wait_http "oe3"      "http://127.0.0.1:${OE3_PORT:-8082}/config.js" oe3

cat <<EOF

────────────────────────────────────────────────────────────
 Stack is up.

   OE3 UI:        http://<host>:${OE3_PORT:-8082}/oe3/
   Broker API:    http://127.0.0.1:${BROKER_API_PORT:-8081}/api/v1
   Broker metrics http://127.0.0.1:${BROKER_API_PORT:-8081}/metrics
   Orthanc REST:  http://127.0.0.1:${ORTHANC_HTTP_PORT:-8042}

   DICOM (modalities → broker): AET ${BROKER_AET:-MWLBROKER}, port ${BROKER_DICOM_PORT:-11113}
   DICOM (direct → orthanc):    AET ${ORTHANC_AET:-ORTHANC}, port ${ORTHANC_DICOM_PORT:-4242}

 Smoke test the MWL path:
   python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 ${BROKER_DICOM_PORT:-11113} ${BROKER_AET:-MWLBROKER}

 Logs:  docker compose logs -f mwl-broker
────────────────────────────────────────────────────────────
EOF
