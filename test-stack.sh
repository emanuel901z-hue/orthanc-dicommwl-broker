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
BROKER_API_URL="${BROKER_API_URL:-http://127.0.0.1:19081}"
# Reachable from inside the compose network but NOT a DICOM endpoint: the
# association hangs until the timeout — exactly what the circuit breaker is for.
DEAD_SOURCE_HOST=orthanc
DEAD_SOURCE_PORT=8042

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

echo "── DICOM smoke: C-STORE routing ──"
# ACC-A-001 belongs to a ris-a worklist item (just C-FIND'd → seen_items)
# and the seeded rule ris-a → pacs-peer must route it to the peer.
python3 mwl-broker/scripts/cstore_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER ACC-A-001 1.2.840.10008.5.1.4.1.1.2.1
# Unknown accession → default target (orthanc).
python3 mwl-broker/scripts/cstore_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER ACC-SMOKE-X 1.2.840.10008.5.1.4.1.1.2.2

peer_count=$(curl -sf http://127.0.0.1:19043/instances | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
orthanc_count=$(curl -sf http://127.0.0.1:19042/instances | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
echo "   pacs-peer instances: $peer_count | orthanc instances: $orthanc_count"
[ "$peer_count" -ge 1 ]   || { echo "FAIL: routed store did not reach pacs-peer" >&2; exit 1; }
[ "$orthanc_count" -ge 1 ] || { echo "FAIL: unrouted store did not reach orthanc (default)" >&2; exit 1; }

echo "── Circuit breaker: dead source trips after repeated failures ──"
curl -sf -X POST "$BROKER_API_URL/api/v1/sources" -H 'Content-Type: application/json' \
  -d "{\"name\":\"e2e-dead\",\"aet\":\"DEAD\",\"host\":\"$DEAD_SOURCE_HOST\",\"port\":$DEAD_SOURCE_PORT,\"calling_aet\":\"MWLBROKER\",\"charset\":\"ISO_IR 100\",\"enabled\":true,\"timeout_s\":1,\"priority\":50}" \
  > /dev/null || true
for _ in 1 2 3 4; do
  python3 mwl-broker/scripts/cfind_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER > /dev/null 2>&1 || true
done
breaker_state=$(curl -sf "$BROKER_API_URL/api/v1/status" | python3 -c "
import json, sys
rows = [s for s in json.load(sys.stdin)['sources'] if s['name'] == 'e2e-dead']
print(rows[0]['breaker_state'] if rows else 'missing')
")
echo "   breaker state for e2e-dead: $breaker_state"
[ "$breaker_state" = "open" ] || { echo "FAIL: circuit breaker did not open" >&2; exit 1; }

findings=$(curl -sf "$BROKER_API_URL/api/v1/health/config" | python3 -c "
import json, sys
print(','.join(f['code'] for f in json.load(sys.stdin)['findings']))
")
echo "   config findings: $findings"
case "$findings" in
  *source_breaker_open*) ;;
  *) echo "FAIL: health checks did not report the open breaker" >&2; exit 1 ;;
esac

ready=$(curl -s -o /dev/null -w '%{http_code}' "$BROKER_API_URL/healthz/ready")
echo "   /healthz/ready -> $ready"
[ "$ready" = "200" ] || { echo "FAIL: readiness probe not ready" >&2; exit 1; }

echo "── Worklist cache: outage bridge ──"
ris_a_id=$(curl -sf "$BROKER_API_URL/api/v1/sources" | python3 -c "
import json, sys
print(next(s['id'] for s in json.load(sys.stdin) if s['name'] == 'ris-a'))
")
# 1. a live query fills the snapshot
python3 mwl-broker/scripts/cfind_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER > /dev/null 2>&1 || true
cached=$(curl -sf "$BROKER_API_URL/api/v1/cache/stats" | python3 -c "
import json, sys
print(sum(row['entries'] for row in json.load(sys.stdin)))
")
echo "   cached worklist items: $cached"
[ "$cached" -ge 3 ] || { echo "FAIL: the cache was not filled by the live query" >&2; exit 1; }

# 2. the RIS becomes unreachable (dead port) — the query must still be answered
curl -sf -X PUT "$BROKER_API_URL/api/v1/sources/$ris_a_id" -H 'Content-Type: application/json' \
  -d "$(curl -sf "$BROKER_API_URL/api/v1/sources" | python3 -c "
import json, sys
row = next(s for s in json.load(sys.stdin) if s['name'] == 'ris-a')
row['port'] = 1
print(json.dumps(row))
")" > /dev/null
python3 mwl-broker/scripts/cfind_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER > /dev/null 2>&1 || true
served_stale=$(curl -sf "$BROKER_API_URL/api/v1/logs/queries?limit=1" | python3 -c "
import json, sys
rows = json.load(sys.stdin)
print(','.join(rows[0].get('served_stale') or []))
")
echo "   served from cache: ${served_stale:-none}"
case "$served_stale" in
  *ris-a*) ;;
  *) echo "FAIL: the outage was not bridged from the cache" >&2; exit 1 ;;
esac
stale_status=$(curl -sf "$BROKER_API_URL/api/v1/logs/queries?limit=1" | python3 -c "
import json, sys
print(json.load(sys.stdin)[0]['status'])
")
echo "   query status while degraded: $stale_status"
[ "$stale_status" = "partial" ] || { echo "FAIL: a stale answer must be 'partial'" >&2; exit 1; }

# 3. restore the source so the Playwright suite sees a healthy stack
curl -sf -X PUT "$BROKER_API_URL/api/v1/sources/$ris_a_id" -H 'Content-Type: application/json' \
  -d "$(curl -sf "$BROKER_API_URL/api/v1/sources" | python3 -c "
import json, sys
row = next(s for s in json.load(sys.stdin) if s['name'] == 'ris-a')
row['port'] = 11114
print(json.dumps(row))
")" > /dev/null

echo "── Playwright (desktop + mobile) ──"
(cd orthanc-explorer-3-usable && OE3_BASE="$OE3_BASE" \
  npx playwright test --config=e2e/stack/playwright.stack.config.ts)

echo "── all checks passed ──"
