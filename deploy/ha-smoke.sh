#!/usr/bin/env bash
# ha-smoke.sh — belegt, dass zwei Broker-Instanzen ein Bild **nicht** doppelt
# zustellen (B1, Hochverfügbarkeit).
#
# Ablauf:
#   1. isolierter Stack (Projekt "mwl-ha", Ports 19xxx) mit dem Profil "ha",
#      also zwei Broker-Instanzen auf gemeinsamer DB und gemeinsamem
#      Spool-Volume
#   2. Ziel auf einen toten Endpunkt zeigen lassen, N Instanzen per C-STORE
#      schicken → sie landen im Spool
#   3. dasselbe Ziel auf den erreichbaren Orthanc umbiegen, beide Instanzen
#      arbeiten lassen
#   4. prüfen: jedes Bild genau **einmal** zugestellt (Store-Log), nichts
#      verloren, beide Instanzen sichtbar
#
#   ./deploy/ha-smoke.sh          # aufbauen, prüfen, abbauen
#   ./deploy/ha-smoke.sh --keep   # Stack danach stehen lassen
#
# Ohne Docker läuft nichts — der Test ist bewusst ein Test des *laufenden*
# Systems, nicht der Unit-Code (den prüft tests/test_ha.py).
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --project-name mwl-ha --env-file .env.test \
  -f docker-compose.yml -f docker-compose.demo.yml --profile ha"

API_A="${API_A:-http://127.0.0.1:19081}"
API_B="${API_B:-http://127.0.0.1:19181}"
DICOM_PORT="${DICOM_PORT:-11123}"
DICOM_AET="${DICOM_AET:-MWLBROKER}"
INSTANCES="${INSTANCES:-24}"

KEEP=0
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

FAILED=()
check() {
  local name="$1" ok="$2" detail="${3:-}"
  if [ "$ok" = "1" ]; then
    echo "PASS  $name${detail:+ — $detail}"
  else
    echo "FAIL  $name${detail:+ — $detail}"
    FAILED+=("$name")
  fi
}

cleanup() {
  if [ "$KEEP" -eq 0 ]; then
    echo "── tearing down ha stack (volumes included) ──"
    $COMPOSE down -v --remove-orphans > /dev/null 2>&1
  else
    echo "── keeping ha stack up (./deploy/ha-smoke.sh down) ──"
  fi
}
trap cleanup EXIT INT TERM

if [ "${1:-}" = "down" ]; then
  $COMPOSE down -v --remove-orphans
  exit 0
fi

api() {  # api <base> <path> [method] [body]
  local base="$1" path="$2" method="${3:-GET}" body="${4:-}"
  if [ -n "$body" ]; then
    curl -sf -X "$method" "$base/api/v1$path" -H 'Content-Type: application/json' -d "$body"
  else
    curl -sf -X "$method" "$base/api/v1$path"
  fi
}

json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

echo "── building + starting the stack with two broker instances ──"
$COMPOSE down -v --remove-orphans > /dev/null 2>&1 || true
$COMPOSE up -d --build > /dev/null

for port in 19081 19181; do
  ready=0
  for _ in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:$port/healthz" > /dev/null 2>&1; then ready=1; break; fi
    sleep 2
  done
  check "Instanz auf Port $port ist bereit" "$ready"
done
[ ${#FAILED[@]} -eq 0 ] || { echo "Stack kam nicht hoch"; exit 1; }

echo "── beide Instanzen sehen sich (Herzschlag) ──"
status_a=$(api "$API_A" /status)
status_b=$(api "$API_B" /status)
id_a=$(echo "$status_a" | json "d['instance_id']")
id_b=$(echo "$status_b" | json "d['instance_id']")
active=$(echo "$status_a" | json "d['instances_active']")
check "Instanz A meldet sich mit eigenem Namen" "$([ "$id_a" != "$id_b" ] && echo 1 || echo 0)" "$id_a"
check "Instanz B meldet sich mit eigenem Namen" "$([ -n "$id_b" ] && echo 1 || echo 0)" "$id_b"
check "beide Instanzen sind aktiv sichtbar" "$([ "$active" -ge 2 ] && echo 1 || echo 0)" "aktiv=$active"

echo "── Ziel auf einen toten Endpunkt zeigen lassen ──"
# `routing` nimmt den *ersten* aktivierten Default — der Seed-Default (Orthanc)
# muss also ausdrücklich ausgeschaltet werden, sonst wird direkt zugestellt und
# der Spool bleibt leer.
python3 - "$API_A" <<'PY'
import json
import sys
import urllib.request

api = sys.argv[1] + "/api/v1"
FIELDS = ("name", "aet", "host", "port", "calling_aet", "is_default", "enabled",
          "tls", "tls_verify", "timeout_s")


def req(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(api + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"null")


for target in req("/targets"):
    if target["is_default"]:
        body = {key: target[key] for key in FIELDS if key in target}
        body["is_default"] = False
        req(f"/targets/{target['id']}", "PUT", body)
        print(f"      Default '{target['name']}' abgeschaltet")

body = {"name": "ha-dead", "aet": "DEAD", "host": "127.0.0.1", "port": 9,
        "calling_aet": "MWLBROKER", "is_default": True, "enabled": True}
created = req("/targets", "POST", body)
print(f"      totes Ziel angelegt: id={created['id']}")
open("/tmp/ha-smoke-target-id", "w").write(str(created["id"]))
PY
dead_id=$(cat /tmp/ha-smoke-target-id)
check "totes Ziel ist der Default" "$([ -n "$dead_id" ] && echo 1 || echo 0)" "id=$dead_id"

# schnelle Wiederholungen, damit der Test nicht Minuten wartet
for pair in "spool_backoff_s=1" "spool_poll_s=1" "spool_max_attempts=100" "spool_lease_s=30"; do
  api "$API_A" "/settings/${pair%%=*}" PUT "{\"value\":\"${pair##*=}\"}" > /dev/null
done

echo "── $INSTANCES Instanzen per C-STORE schicken (Ziel tot → Spool) ──"
python3 mwl-broker/scripts/loadtest.py cstore --host 127.0.0.1 --port "$DICOM_PORT" \
  --aet "$DICOM_AET" --api "$API_A" --instances "$INSTANCES" --concurrency 4 \
  --accession ACC-HA --study-uid 1.2.826.0.1.3680043.8.498.4242 > /tmp/ha-smoke-cstore.txt 2>&1
tail -4 /tmp/ha-smoke-cstore.txt

spool_open=$(api "$API_A" /spool/stats | json "d['open']")
check "alle $INSTANCES liegen im Spool" "$([ "$spool_open" -ge "$INSTANCES" ] && echo 1 || echo 0)" "open=$spool_open"
check "der Spool ist für beide Instanzen derselbe" \
  "$([ "$(api "$API_B" /spool/stats | json "d['open']")" = "$spool_open" ] && echo 1 || echo 0)" \
  "A=$spool_open B=$(api "$API_B" /spool/stats | json "d['open']")"

echo "── dasselbe Ziel auf Orthanc umbiegen — beide Instanzen arbeiten ──"
# Der Eintrag behält seine ID (und damit die Zuordnung im Spool); nur der
# Endpunkt wird erreichbar.
python3 - "$API_A" "$dead_id" <<'PY'
import json
import sys
import urllib.request

api = sys.argv[1] + "/api/v1"
target_id = sys.argv[2]
body = {"name": "ha-dead", "aet": "ORTHANC", "host": "orthanc", "port": 4242,
        "calling_aet": "MWLBROKER", "is_default": True, "enabled": True}
request = urllib.request.Request(f"{api}/targets/{target_id}",
                                 data=json.dumps(body).encode(), method="PUT",
                                 headers={"Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=10) as response:
    json.loads(response.read() or b"null")
print("      Ziel zeigt jetzt auf Orthanc")
PY

delivered=0
for _ in $(seq 1 60); do
  open_now=$(api "$API_A" /spool/stats | json "d['open']")
  if [ "$open_now" = "0" ]; then delivered=1; break; fi
  sleep 2
done
check "der Spool ist leer (alles zugestellt)" "$delivered" "open=$(api "$API_A" /spool/stats | json "d['open']")"

echo "── genau einmal zugestellt? ──"
# Zwei unabhängige Zeugen:
#  * Orthanc hat alle Bilder (nichts verloren)
#  * die Summe der erfolgreichen Zustellungen über BEIDE Instanzen ist genau N —
#    jede Zustellung erhöht den Zähler einmal, ein Duplikat würde ihn zweimal
#    erhöhen. Der Store-Log taugt dafür nicht: er protokolliert den Live-Pfad
#    (Modalität → Broker), nicht die spätere Spool-Zustellung.
metrics_a=$(curl -sf "$API_A/metrics")
metrics_b=$(curl -sf "$API_B/metrics")
forwarded=$(printf '%s\n%s\n' "$metrics_a" "$metrics_b" \
  | awk '/^mwl_spool_forwarded_total/ {sum += $2} END {print sum + 0}')
claimed=$(printf '%s\n%s\n' "$metrics_a" "$metrics_b" \
  | awk '/^mwl_spool_claimed_total/ {sum += $2} END {print sum + 0}')
per_instance=$(printf '%s\n%s\n' "$metrics_a" "$metrics_b" \
  | awk '/^mwl_spool_forwarded_total/ {print "        " $0}')
orthanc=$(curl -sf "http://127.0.0.1:${ORTHANC_HTTP_PORT:-19042}/instances" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

check "jede Instanz wurde genau einmal zugestellt" \
  "$([ "${forwarded%%.*}" = "$INSTANCES" ] && echo 1 || echo 0)" \
  "Zustellungen=$forwarded erwartet=$INSTANCES"
check "Orthanc hat alle Bilder (nichts verloren)" \
  "$([ "$orthanc" -ge "$INSTANCES" ] && echo 1 || echo 0)" "Orthanc=$orthanc"
check "jeder Eintrag wurde genau einmal beansprucht" \
  "$([ "${claimed%%.*}" -ge "$INSTANCES" ] && echo 1 || echo 0)" "Claims=$claimed"
echo "      Zustellungen je Instanz:"
echo "$per_instance"

echo ""
echo "════════════════════════════════════════"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "HA-SMOKE: alle Prüfungen bestanden"
  exit 0
else
  echo "HA-SMOKE: fehlgeschlagen: ${FAILED[*]}"
  exit 1
fi
