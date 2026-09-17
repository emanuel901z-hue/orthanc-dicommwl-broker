#!/usr/bin/env bash
# test-stack.sh — ephemeral full-stack e2e run.
#
# Brings up an isolated copy of the stack (project "mwl-test", ports 19xxx/
# 14xxx) via .env.test, waits for health, runs the DICOM smoke test and the
# Playwright browser suite against it, then tears everything down incl.
# volumes. Safe to run next to the regular mwl-broker stack.
#
#   ./test-stack.sh            # up + tests + down
#   ./test-stack.sh --keep     # leave the test stack running afterwards
#   ./test-stack.sh --down     # just tear down a previously kept stack
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE="docker compose --project-name mwl-test --env-file .env.test \
  -f docker-compose.yml -f docker-compose.demo.yml"

OE3_BASE="${OE3_BASE:-http://127.0.0.1:19082}"
BROKER_DICOM_HOST=127.0.0.1
BROKER_DICOM_PORT=11123

KEEP=0
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    --down) exec $COMPOSE down -v ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

cleanup() {
  if [ "$KEEP" -eq 0 ]; then
    echo "── tearing down test stack (volumes included) ──"
    $COMPOSE down -v --remove-orphans
  else
    echo "── keeping test stack up (./test-stack.sh --down to remove) ──"
  fi
}
trap cleanup EXIT

echo "── building + starting test stack ──"
$COMPOSE up -d --build

echo "── waiting for broker health ──"
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:19081/healthz >/dev/null 2>&1; then
    echo "   broker healthy after ~$((i * 2))s"
    break
  fi
  [ "$i" = "60" ] && { echo "broker never became healthy" >&2; $COMPOSE logs mwl-broker | tail -30; exit 1; }
  sleep 2
done

echo "── waiting for OE3 ──"
for i in $(seq 1 30); do
  curl -sf "$OE3_BASE/oe3/" -o /dev/null && break || sleep 2
done

echo "── DICOM smoke: C-FIND through broker ──"
python3 mwl-broker/scripts/cfind_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER

echo "── Playwright (desktop + mobile) ──"
(cd orthanc-explorer-3-usable && OE3_BASE="$OE3_BASE" \
  npx playwright test --config=e2e/stack/playwright.stack.config.ts)

echo "── all checks passed ──"
