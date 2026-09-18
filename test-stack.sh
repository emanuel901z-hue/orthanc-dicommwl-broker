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
BROKER_TLS_PORT=19083
BROKER_AET=MWLBROKER
# the broker checks its own listener from inside the container
BROKER_TLS_INTERNAL_PORT=2762
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
# start from a clean database: the scenarios below (local items, station rules,
# spool entries) are not idempotent by nature, and a leftover volume would make
# the assertions depend on the previous run
$COMPOSE down -v --remove-orphans > /dev/null 2>&1 || true
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

echo "── Alerting: webhook delivery ──"
# A tiny receiver on the host — the broker reaches it via host.docker.internal.
WEBHOOK_LOG=$(mktemp)
WEBHOOK_PORT=19999
python3 - "$WEBHOOK_LOG" "$WEBHOOK_PORT" <<'PY' &
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

log_path, port = sys.argv[1], int(sys.argv[2])

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        with open(log_path, "a") as handle:
            handle.write(body.decode("utf-8", "replace") + "\n")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass

HTTPServer(("0.0.0.0", port), Handler).serve_forever()
PY
WEBHOOK_PID=$!
trap 'kill $WEBHOOK_PID 2>/dev/null; rm -f "$WEBHOOK_LOG"' EXIT
sleep 1

curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/notify_webhook_url" \
  -H 'Content-Type: application/json' \
  -d "{\"value\":\"http://host.docker.internal:$WEBHOOK_PORT/hook\"}" > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/notify_events" \
  -H 'Content-Type: application/json' \
  -d '{"value":"source_down,target_down,spool_dead_letter,breaker_open,spool_full,config_error"}' > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/notify_min_interval_s" \
  -H 'Content-Type: application/json' -d '{"value":"0"}' > /dev/null

test_result=$(curl -sf -X POST "$BROKER_API_URL/api/v1/notify/test")
echo "   test message: $test_result"
case "$test_result" in
  *'"ok":true'*) ;;
  *) echo "FAIL: the webhook did not accept the test message" >&2; exit 1 ;;
esac
[ -s "$WEBHOOK_LOG" ] || { echo "FAIL: the webhook receiver got nothing" >&2; exit 1; }

echo "── ATNA: audit trail to an own repository ──"
# A plain-TCP syslog receiver on the host stands in for the hospital's ARR.
ATNA_LOG=$(mktemp)
ATNA_PORT=19998
python3 - "$ATNA_LOG" "$ATNA_PORT" <<'PY' &
import socket, sys, threading

log_path, port = sys.argv[1], int(sys.argv[2])
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", port))
server.listen(8)

def handle(conn):
    with conn:
        conn.settimeout(2)
        data = b""
        try:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
    if data:
        with open(log_path, "ab") as handle_file:
            handle_file.write(data + b"\n")

while True:
    conn, _ = server.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
PY
ATNA_PID=$!
trap 'kill $WEBHOOK_PID $ATNA_PID 2>/dev/null; rm -f "$WEBHOOK_LOG" "$ATNA_LOG" "$TLS_CA_FILE"' EXIT
sleep 1

curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/atna_syslog_host" \
  -H 'Content-Type: application/json' -d '{"value":"host.docker.internal"}' > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/atna_syslog_port" \
  -H 'Content-Type: application/json' -d "{\"value\":\"$ATNA_PORT\"}" > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/atna_syslog_protocol" \
  -H 'Content-Type: application/json' -d '{"value":"tcp"}' > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/atna_enabled" \
  -H 'Content-Type: application/json' -d '{"value":"true"}' > /dev/null

atna_test=$(curl -sf -X POST "$BROKER_API_URL/api/v1/atna/test")
echo "   test audit message: $atna_test"
case "$atna_test" in
  *'"ok":true'*) ;;
  *) echo "FAIL: the audit repository did not accept the test message" >&2; exit 1 ;;
esac
atna_sample=$(curl -sf "$BROKER_API_URL/api/v1/atna/sample" | python3 -c "import json,sys; print(json.load(sys.stdin)['xml'][:40])")
echo "   sample message: $atna_sample"

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

echo "── C-STORE spool: store and forward ──"
# The default target (orthanc) is taken down: the broker must spool the
# instance instead of losing it and still confirm it to the modality.
orthanc_target_id=$(curl -sf "$BROKER_API_URL/api/v1/targets" | python3 -c "
import json, sys
print(next(t['id'] for t in json.load(sys.stdin) if t['name'] == 'orthanc'))
")
set_target_port() {
  curl -sf -X PUT "$BROKER_API_URL/api/v1/targets/$orthanc_target_id" \
    -H 'Content-Type: application/json' \
    -d "$(curl -sf "$BROKER_API_URL/api/v1/targets" | python3 -c "
import json, sys
row = next(t for t in json.load(sys.stdin) if t['id'] == $orthanc_target_id)
row['port'] = $1
print(json.dumps(row))
")" > /dev/null
}

set_target_port 1                       # nothing listens there
python3 mwl-broker/scripts/cstore_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER ACC-SPOOL-1 1.2.840.10008.5.1.4.1.1.2.3
queued=$(curl -sf "$BROKER_API_URL/api/v1/spool/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['open'])")
echo "   queued after a failed forward: $queued"
[ "$queued" -ge 1 ] || { echo "FAIL: the instance was not spooled" >&2; exit 1; }

# The target recovers → the retry worker delivers the instance.
set_target_port 4242
delivered=0
for _ in $(seq 1 12); do
  sleep 3
  open=$(curl -sf "$BROKER_API_URL/api/v1/spool/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['open'])")
  if [ "$open" -eq 0 ]; then delivered=1; break; fi
done
echo "   backlog after recovery: $(curl -sf "$BROKER_API_URL/api/v1/spool/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['open'])")"
[ "$delivered" -eq 1 ] || { echo "FAIL: the spooled instance was never delivered" >&2; exit 1; }

# Leave one *dead letter* for the UI test: the target is down while the worker
# retries, and the test stack dead-letters after the first attempt. The target
# is restored afterwards, so the rest of the suite sees a healthy stack.
set_target_port 1
python3 mwl-broker/scripts/cstore_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER ACC-SPOOL-2 1.2.840.10008.5.1.4.1.1.2.4
dead=0
for _ in $(seq 1 15); do
  sleep 2
  dead=$(curl -sf "$BROKER_API_URL/api/v1/spool/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['dead'])")
  if [ "$dead" -ge 1 ]; then break; fi
done
set_target_port 4242
echo "   dead letters for the UI test: $dead"
[ "$dead" -ge 1 ] || { echo "FAIL: no dead letter was produced" >&2; exit 1; }

echo "── DICOM TLS: a certified C-FIND ──"
# the generated certificate is copied out of the container so the smoke client
# can verify it as well
TLS_CA_FILE=$(mktemp)
# Generate a certificate for the broker, enable the TLS listener and run a real
# TLS C-FIND against it — the staged rollout a modality would go through.
tls_cert=$(curl -sf -X POST "$BROKER_API_URL/api/v1/tls/self-signed" \
  -H 'Content-Type: application/json' \
  -d '{"common_name":"127.0.0.1","days":365,"san":["127.0.0.1","host.docker.internal"]}')
tls_cert_path=$(echo "$tls_cert" | python3 -c "import json,sys; print(json.load(sys.stdin)['certificate_path'])")
tls_key_path=$(echo "$tls_cert" | python3 -c "import json,sys; print(json.load(sys.stdin)['key_path'])")
echo "$tls_cert" | python3 -c "import json,sys; d=json.load(sys.stdin); print('   generated:', d['certificate']['subject'], '| days left:', d['certificate']['days_left'])"

curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/tls_inbound_cert_file" \
  -H 'Content-Type: application/json' -d "{\"value\":\"$tls_cert_path\"}" > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/tls_inbound_key_file" \
  -H 'Content-Type: application/json' -d "{\"value\":\"$tls_key_path\"}" > /dev/null
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/tls_inbound_enabled" \
  -H 'Content-Type: application/json' -d '{"value":"true"}' > /dev/null
# the operator's next step: trust the generated certificate (the same file works
# as its own CA here) — then verification can stay on
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/tls_outbound_ca_file" \
  -H 'Content-Type: application/json' -d "{\"value\":\"$tls_cert_path\"}" > /dev/null
echo "$tls_cert" | python3 -c "import json,sys; print(json.load(sys.stdin)['certificate_pem'], end='')" > "$TLS_CA_FILE"
# the listener starts with the next association; the broker is restarted here so
# the test proves the startup path as well
$COMPOSE restart mwl-broker > /dev/null 2>&1
for i in $(seq 1 30); do
  curl -sf "$BROKER_API_URL/healthz" >/dev/null 2>&1 && break
  sleep 1
done
sleep 2

tls_overview=$(curl -sf "$BROKER_API_URL/api/v1/tls/overview" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('listener', d['inbound_enabled'], 'port', d['inbound_port'],
      'client-auth', d['inbound_client_auth'])")
echo "   $tls_overview"
case "$tls_overview" in
  "listener True"*) ;;
  *) echo "FAIL: the TLS listener is not enabled" >&2; exit 1 ;;
esac

# trust the generated certificate and query the TLS port
curl -sf "$BROKER_API_URL/api/v1/tls/overview" > /dev/null
tls_answers=$(python3 mwl-broker/scripts/cfind_smoke.py "$BROKER_DICOM_HOST" "$BROKER_TLS_PORT" MWLBROKER --tls --ca "$TLS_CA_FILE" 2>&1 | grep -c 'acc=' || true)
echo "   C-FIND over TLS: $tls_answers answer(s)"
[ "$tls_answers" -ge 1 ] || { echo "FAIL: no answers over TLS" >&2; exit 1; }

tls_check=$(curl -sf -X POST "$BROKER_API_URL/api/v1/tls/test" \
  -H 'Content-Type: application/json' \
  -d "{\"host\":\"127.0.0.1\",\"port\":$BROKER_TLS_INTERNAL_PORT,\"echo_aet\":\"$BROKER_AET\"}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['protocol'], d['ok'], 'echo', d['echo_ok'])")
echo "   endpoint check: $tls_check"
case "$tls_check" in
  TLSv1*) ;;
  *) echo "FAIL: the TLS endpoint check did not succeed" >&2; exit 1 ;;
esac

echo "── RBAC: read-only vs. write role ──"
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/rbac_mode" \
  -H 'Content-Type: application/json' -H 'X-OE3-Roles: brokerWrite' \
  -d '{"value":"enforce"}' > /dev/null

denied=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BROKER_API_URL/api/v1/sources" \
  -H 'Content-Type: application/json' -d '{"name":"denied","aet":"DENIED","host":"h","port":1}')
echo "   write without the role: $denied"
[ "$denied" = "403" ] || { echo "FAIL: a read-only caller could write" >&2; exit 1; }

allowed=$(curl -s -X POST "$BROKER_API_URL/api/v1/sources" \
  -H 'Content-Type: application/json' -H 'X-OE3-Roles: brokerWrite' \
  -d '{"name":"denied-check","aet":"DENIED","host":"127.0.0.1","port":1,"calling_aet":"MWLBROKER","charset":"ISO_IR 100"}')
allowed_name=$(echo "$allowed" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('name', d.get('detail', '?')))" 2>/dev/null || echo "error")
echo "   write with the role: $allowed_name"
[ "$allowed_name" = "denied-check" ] || { echo "FAIL: the write with the role did not work" >&2; exit 1; }
rbac_status=$(curl -sf "$BROKER_API_URL/api/v1/rbac/status" -H 'X-OE3-Roles: brokerRead' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['enforced'], d['can_write'])")
echo "   rbac status (read-only caller): $rbac_status"
case "$rbac_status" in
  "True False") ;;
  *) echo "FAIL: the read-only caller is not reported as such" >&2; exit 1 ;;
esac
curl -sf -X PUT "$BROKER_API_URL/api/v1/settings/rbac_mode" \
  -H 'Content-Type: application/json' -H 'X-OE3-Roles: brokerWrite' \
  -d '{"value":"off"}' > /dev/null

echo "── Local worklist items + HL7 ORM ──"
# A locally scheduled emergency must appear in the worklist the modality gets.
curl -s -X POST "$BROKER_API_URL/api/v1/local-items" -H 'Content-Type: application/json' -d '{
  "accession":"EMERG-E2E","sps_id":"1","patient_id":"P7777","patient_name":"Notfall^Erika",
  "modality":"CT","station_aet":"CT_01","procedure_description":"CT Schaedel (Notfall)",
  "scheduled_date":"2026-09-17"}' > /dev/null
local_count=$(curl -sf "$BROKER_API_URL/api/v1/local-items" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
echo "   local items: $local_count"
[ "$local_count" -ge 1 ] || { echo "FAIL: the local item was not created" >&2; exit 1; }

python3 mwl-broker/scripts/cfind_smoke.py "$BROKER_DICOM_HOST" "$BROKER_DICOM_PORT" MWLBROKER > /tmp/cfind-local.txt 2>&1 || true
grep -q "EMERG-E2E" /tmp/cfind-local.txt || { echo "FAIL: the local item is missing from the C-FIND answers" >&2; exit 1; }
echo "   C-FIND answers: $(grep -c 'acc=' /tmp/cfind-local.txt) (incl. the local emergency)"

# The HL7 interface: dry-run, then apply.
ORM='MSH|^~\&|RIS|HOSPITAL|MWLBROKER|RAD|20260917103000||ORM^O01|E2E1|P|2.5
PID|1||P8888||Weber^Karl||19700101|M
ORC|NW|P1|F1
OBR|1|P1|ACC-HL7-E2E|DX^Thorax p.a.|R|20260918101500
ZDS|1.2.3.4.5|XR_01'
orm_dry=$(curl -sf -X POST "$BROKER_API_URL/api/v1/hl7/orm?dry_run=true" \
  -H 'Content-Type: text/plain' --data-binary "$ORM" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['accession'], d['order_control'], d['action'])")
echo "   HL7 dry-run: $orm_dry"
orm_apply=$(curl -sf -X POST "$BROKER_API_URL/api/v1/hl7/orm?dry_run=false" \
  -H 'Content-Type: text/plain' --data-binary "$ORM" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['accession'], d['action'])")
echo "   HL7 apply: $orm_apply"
case "$orm_apply" in
  *created*|*updated*) ;;
  *) echo "FAIL: the HL7 order was not applied" >&2; exit 1 ;;
esac

echo "── Station rules ──"
rule_id=$(curl -s -X POST "$BROKER_API_URL/api/v1/station-rules" -H 'Content-Type: application/json' -d '{
  "name":"e2e-ct-hides-ris-b","station_aet":"CT_01","mode":"deny","source_ids":[]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id', 'existing'))")
station_preview=$(curl -sf -X POST "$BROKER_API_URL/api/v1/simulate/station" \
  -H 'Content-Type: application/json' -d '{"station_aet":"CT_01"}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['rule_name'], len(d['sources']))")
echo "   station preview: $station_preview"
case "$station_preview" in
  e2e-ct-hides-ris-b*) ;;
  *) echo "FAIL: the station rule was not matched" >&2; exit 1 ;;
esac
echo "   (rule $rule_id stays for the UI test)"

echo "── Alerting: an event reached the webhook ──"
events=""
for _ in $(seq 1 20); do
  sleep 2
  events=$(python3 - "$WEBHOOK_LOG" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as handle:
        codes = {json.loads(line).get("event") for line in handle if line.strip()}
except FileNotFoundError:
    codes = set()
print(",".join(sorted(c for c in codes if c)))
PY
)
  case "$events" in
    *spool_dead_letter*|*target_down*|*source_down*) break ;;
  esac
done
echo "   events received: $events"
case "$events" in
  *spool_dead_letter*|*target_down*|*source_down*) ;;
  *) echo "FAIL: no real broker event was delivered" >&2; exit 1 ;;
esac
# the receivers stay up: the Playwright suite sends test messages from the UI

echo "── ATNA: a real audit message was delivered ──"
sleep 3
if grep -aq 'csd-code="110112"' "$ATNA_LOG" 2>/dev/null; then
  echo "   audit messages received: $(grep -ac 'AuditMessage' "$ATNA_LOG") (Query events included)"
else
  echo "   audit messages received: $(grep -ac 'AuditMessage' "$ATNA_LOG" || echo 0)"
  echo "FAIL: no Query audit message reached the repository" >&2
  exit 1
fi

echo "── Playwright (desktop + mobile) ──"
(cd orthanc-explorer-3-usable && OE3_BASE="$OE3_BASE" \
  npx playwright test --config=e2e/stack/playwright.stack.config.ts)

echo "── all checks passed ──"
