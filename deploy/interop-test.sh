#!/usr/bin/env bash
# interop-test.sh — externe Kompatibilitätsprüfung mit **Fremdsoftware** (E1, Teil 1)
#
# Der Broker ist bisher immer gegen *unseren eigenen* Mock geprüft worden
# (`mwl_broker/mock_ris.py`) — die DIMSE-Gegenstellen waren also unser Code.
# Dieses Skript stellt echte Fremdimplementierungen gegenüber, mit **DCMTK**
# (OFFIS, seit Jahrzehnten verbreitet, hier als Ubuntu-Paket vorhanden):
#
#   wlmscpfs   → fremdes RIS (Modality Worklist SCP), speist sich aus einer
#                DCMTK-Beispiel-Worklist (10 Einträge)
#   dcmqrscp   → fremdes PACS (C-STORE SCP)
#   findscu -W → fremde Modalität, die unsere Arbeitsliste abfragt
#   storescu   → fremde Modalität, die ein Bild schickt
#   echoscu    → fremde Modalität, die C-ECHO macht
#   dcmdump    → fremder Decoder: was tatsächlich angekommen ist
#
#   ./deploy/interop-test.sh          # aufbauen, prüfen, abbauen
#   ./deploy/interop-test.sh --keep   # Stack danach stehen lassen
#   ./deploy/interop-test.sh down     # einen stehen gelassenen Stack abbauen
#
# Läuft gegen den isolierten Test-Stack (Projekt "mwl-interop", Ports 19xxx).
# Die DCMTK-Werkzeuge laufen auf dem **Host**; der Broker erreicht sie über
# `host.docker.internal`.
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --project-name mwl-interop --env-file .env.test -f docker-compose.yml"

API="${API:-http://127.0.0.1:19081}"
BROKER_DICOM_PORT="${BROKER_DICOM_PORT:-11123}"
BROKER_AET="${BROKER_AET:-MWLBROKER}"
WLM_PORT="${WLM_PORT:-11116}"        # fremdes RIS   (wlmscpfs)
PACS_PORT="${PACS_PORT:-11117}"      # fremdes PACS  (dcmqrscp)
WLM_AET="${WLM_AET:-OFFIS}"          # DCMTK-Beispiel-Worklist läuft unter OFFIS
PACS_AET="${PACS_AET:-DCMTK_PACS}"
WORK="${WORK:-/tmp/mwl-interop}"

KEEP=0
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    down) exec $COMPOSE down -v --remove-orphans ;;
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
    pkill -x wlmscpfs 2>/dev/null
    pkill -x dcmqrscp 2>/dev/null
    echo "── tearing down interop stack (volumes included) ──"
    $COMPOSE down -v --remove-orphans > /dev/null 2>&1
  else
    echo "── keeping the stack up (./deploy/interop-test.sh down) ──"
    echo "   fremdes RIS:  ${WLM_AET}@127.0.0.1:${WLM_PORT}"
    echo "   fremdes PACS: ${PACS_AET}@127.0.0.1:${PACS_PORT} (Ablage: ${WORK}/pacs)"
  fi
}
trap cleanup EXIT INT TERM

api() {
  local path="$1" method="${2:-GET}" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sf -X "$method" "$API/api/v1$path" -H 'Content-Type: application/json' -d "$body"
  else
    curl -sf -X "$method" "$API/api/v1$path"
  fi
}

# ── Vorprüfung: die Fremdsoftware muss da sein ────────────────────────────
echo "── Fremdsoftware prüfen (DCMTK) ──"
missing=()
for tool in wlmscpfs dcmqrscp findscu storescu echoscu dump2dcm dcmdump; do
  command -v "$tool" > /dev/null 2>&1 || missing+=("$tool")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "DCMTK fehlt: ${missing[*]}"
  echo "Installieren mit: sudo apt install dcmtk"
  exit 2
fi
echo "   $(dcmtk --version 2>/dev/null | head -1 || wlmscpfs --version 2>/dev/null | head -1)"

# ── fremdes RIS: Worklist-Datenbank aus den DCMTK-Beispielen ──────────────
echo "── fremdes RIS aufbauen (wlmscpfs + DCMTK-Beispiel-Worklist) ──"
rm -rf "$WORK"
mkdir -p "$WORK/wlmdb/$WLM_AET" "$WORK/pacs"
EXAMPLE=/usr/share/doc/dcmtk/examples/wlistdb
if [ ! -d "$EXAMPLE/$WLM_AET" ]; then
  echo "DCMTK-Beispiel-Worklist fehlt ($EXAMPLE/$WLM_AET)"
  exit 2
fi
cp "$EXAMPLE/$WLM_AET/lockfile" "$WORK/wlmdb/$WLM_AET/" 2>/dev/null || touch "$WORK/wlmdb/$WLM_AET/lockfile"
converted=0
for f in "$EXAMPLE/$WLM_AET"/*.dump; do
  # die Beispiele sind CSV-Text; wlmscpfs will DICOM-Dateien mit Suffix .wl
  dump2dcm -g "$f" "$WORK/wlmdb/$WLM_AET/$(basename "$f" .dump).wl" > /dev/null 2>&1 && converted=$((converted + 1))
done
check "fremde Worklist vorbereitet" "$([ "$converted" -ge 1 ] && echo 1 || echo 0)" "$converted Einträge"

# ── fremdes PACS: Konfiguration ───────────────────────────────────────────
# `ANY` als erlaubte Calling-AET: eine namentliche Liste hat DCMTK hier
# abgelehnt ("Called AE Title Not Recognized"), auch mit HostTable-Eintrag.
cat > "$WORK/dcmqrscp.cfg" <<EOF
NetworkTCPPort  = $PACS_PORT
MaxPDUSize      = 16384
MaxAssociations = 8
HostTable BEGIN
HostTable END
VendorTable BEGIN
VendorTable END
AETable BEGIN
$PACS_AET $WORK/pacs RW (9, 1024mb) ANY
AETable END
EOF

# ── Stack hochziehen ──────────────────────────────────────────────────────
echo "── Broker-Stack starten (isoliert) ──"
$COMPOSE down -v --remove-orphans > /dev/null 2>&1 || true
$COMPOSE up -d --build > /dev/null
ready=0
for _ in $(seq 1 60); do
  if curl -sf "$API/healthz" > /dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
check "Broker ist bereit" "$ready"
[ "$ready" = "1" ] || { echo "Stack kam nicht hoch"; exit 1; }

# Der Broker läuft im Compose-Netz dieses Projekts; `host.docker.internal`
# zeigt per Compose-Vorgabe auf docker0 (172.17.0.1) und damit auf ein fremdes
# Netz. Die richtige Host-Adresse ist das Gateway *dieses* Netzwerks.
HOST_FOR_CONTAINER=$(docker network inspect mwl-interop_default \
  -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null)
[ -n "$HOST_FOR_CONTAINER" ] || HOST_FOR_CONTAINER=host.docker.internal
echo "   Host-Adresse für den Broker: $HOST_FOR_CONTAINER"

# ── Fremdsoftware starten ─────────────────────────────────────────────────
echo "── Fremdsoftware starten ──"
# Reste eines früheren Laufs zuerst weg: sie halten die Ports und arbeiten
# sonst mit einem Ablageverzeichnis, das dieser Lauf gerade gelöscht hat.
pkill -x wlmscpfs 2>/dev/null
pkill -x dcmqrscp 2>/dev/null
sleep 1
nohup wlmscpfs -dfp "$WORK/wlmdb" "$WLM_PORT" > "$WORK/wlmscpfs.log" 2>&1 & disown
nohup dcmqrscp --config "$WORK/dcmqrscp.cfg" "$PACS_PORT" > "$WORK/dcmqrscp.log" 2>&1 & disown
sleep 3
check "fremdes RIS antwortet (C-ECHO an $WLM_AET)" \
  "$(echoscu 127.0.0.1 "$WLM_PORT" -aec "$WLM_AET" -aet "$BROKER_AET" > /dev/null 2>&1 && echo 1 || echo 0)"
check "fremdes PACS antwortet (C-ECHO an $PACS_AET)" \
  "$(echoscu 127.0.0.1 "$PACS_PORT" -aec "$PACS_AET" -aet "$BROKER_AET" > /dev/null 2>&1 && echo 1 || echo 0)"

# ── Broker an die Fremdsoftware anschließen ───────────────────────────────
echo "── Broker mit der Fremdsoftware verbinden ──"
source_id=$(api /sources POST "{\"name\":\"dcmtk-wlm\",\"aet\":\"$WLM_AET\",\"host\":\"host.docker.internal\",\"port\":$WLM_PORT,\"calling_aet\":\"$BROKER_AET\",\"charset\":\"ISO_IR 100\",\"enabled\":true,\"timeout_s\":10,\"priority\":1}" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
target_id=$(api /targets POST "{\"name\":\"dcmtk-pacs\",\"aet\":\"$PACS_AET\",\"host\":\"host.docker.internal\",\"port\":$PACS_PORT,\"calling_aet\":\"$BROKER_AET\",\"is_default\":false,\"enabled\":true}" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
api /rules POST "{\"source_id\":$source_id,\"target_id\":$target_id,\"priority\":1}" > /dev/null
check "Quelle + Ziel + Regel angelegt" \
  "$([ -n "$source_id" ] && [ -n "$target_id" ] && echo 1 || echo 0)" "source=$source_id target=$target_id"

echo "── Unser Broker fragt das fremde RIS (unser SCU gegen Fremdcode) ──"
probe=$(api "/sources/$source_id/query" POST '{}')
probe_answers=$(printf '%s' "$probe" | python3 -c "import json,sys; print(json.load(sys.stdin).get('answers', 0))" 2>/dev/null)
check "unser Upstream-Client liest die fremde Worklist" \
  "$([ "${probe_answers:-0}" -ge 10 ] && echo 1 || echo 0)" "Antworten: ${probe_answers:-0}"

echo "── Fremde Modalität fragt den Broker (C-FIND MWL) ──"
findscu -W -k "0008,0050=" -k "0010,0010=" -k "0040,0100" \
  127.0.0.1 "$BROKER_DICOM_PORT" -aec "$BROKER_AET" -aet "DCMTK_MOD" \
  > "$WORK/cfind.out" 2>&1
# DCMTK druckt je Antwort eine Pending-Zeile: die fremde Modalität muss genau
# die Einträge der fremden Worklist sehen (das DCMTK-Beispiel hat zehn)
found=$(grep -c "Pending" "$WORK/cfind.out" || true)
check "die fremde Modalität bekommt die fremde Arbeitsliste" \
  "$([ "${found:-0}" -ge 10 ] && echo 1 || echo 0)" "${found:-0} von 10 Einträgen"
# die Daten stammen nachweislich aus der fremden Worklist (DCMTK-Beispielwerte)
check "die Antwort enthält die Daten des fremden RIS" \
  "$(grep -qE "VIVALDI|HAYDN|MOZART" "$WORK/cfind.out" && echo 1 || echo 0)" \
  "$(grep -oE "VIVALDI\^[A-Z]+|HAYDN\^[A-Z]+|MOZART\^[A-Z]+" "$WORK/cfind.out" | head -2 | tr '\n' ' ')"
# und der Broker hat die fremde Quelle dabei wirklich befragt (Query-Log)
logged=$(api '/logs/queries?limit=5' | python3 -c "
import json,sys
for row in json.load(sys.stdin):
    per = row.get('per_source') or {}
    if 'dcmtk-wlm' in per:
        print(per['dcmtk-wlm']); break
else:
    print('none')")
check "die Abfrage hat das fremde RIS erreicht (Query-Log)" \
  "$([ "$logged" != "none" ] && [ "$logged" != "error" ] && echo 1 || echo 0)" "per_source: $logged"

echo "── Fremde Modalität schickt ein Bild (C-STORE → Routing → fremdes PACS) ──"
# Accession 00003 stammt aus der fremden Worklist, die der Broker gerade
# beantwortet hat — die Routing-Herkunft zeigt also auf das fremde RIS.
python3 - "$WORK/cstore.dcm" <<'PY'
import sys
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

sop = generate_uid()
meta = FileMetaDataset()
meta.MediaStorageSOPClassUID = CTImageStorage
meta.MediaStorageSOPInstanceUID = sop
meta.TransferSyntaxUID = ExplicitVRLittleEndian
ds = FileDataset(sys.argv[1], {}, file_meta=meta, preamble=b"\0" * 128)
ds.SOPClassUID = CTImageStorage
ds.SOPInstanceUID = sop
ds.StudyInstanceUID = generate_uid()
ds.SeriesInstanceUID = generate_uid()
ds.AccessionNumber = "00003"          # aus der DCMTK-Worklist
ds.PatientID = "INTEROP-1"
ds.PatientName = "Interop^Test"
ds.Modality = "CT"
ds.SeriesNumber = "1"
ds.InstanceNumber = "1"
ds.Rows = 4
ds.Columns = 4
ds.BitsAllocated = 16
ds.BitsStored = 16
ds.HighBit = 15
ds.PixelRepresentation = 0
ds.PhotometricInterpretation = "MONOCHROME2"
ds.SamplesPerPixel = 1
ds.PixelData = b"\0" * 32
ds.save_as(sys.argv[1], enforce_file_format=True)
print(sop)
PY
storescu 127.0.0.1 "$BROKER_DICOM_PORT" -aec "$BROKER_AET" -aet "DCMTK_MOD" \
  "$WORK/cstore.dcm" > "$WORK/cstore.out" 2>&1
store_ok=$?
check "die fremde Modalität bekommt den Store bestätigt" "$([ "$store_ok" -eq 0 ] && echo 1 || echo 0)" \
  "$(grep -oE 'Status: [0-9A-Fa-fx]+' "$WORK/cstore.out" | tail -1 || echo "exit=$store_ok")"

arrived=$(find "$WORK/pacs" -name "CT_*.dcm" -type f | wc -l)
check "das Bild liegt im fremden PACS" "$([ "$arrived" -ge 1 ] && echo 1 || echo 0)" "$arrived Datei(en)"
# unabhängig dekodiert: nicht mit pydicom, sondern mit DCMTK
if [ "$arrived" -ge 1 ]; then
  decoded=$(dcmdump "$(find "$WORK/pacs" -name "CT_*.dcm" -type f | head -1)" 2>/dev/null)
  check "der fremde Decoder liest die weitergeleiteten Daten" \
    "$(printf '%s' "$decoded" | grep -q "INTEROP-1" && echo 1 || echo 0)" \
    "$(printf '%s' "$decoded" | grep -E 'AccessionNumber|PatientID' | head -2 | tr -s ' ' | tr '\n' ' ' | cut -c1-70)"
fi

echo "── Unser Broker als SCP gegen die fremde Modalität (C-ECHO) ──"
check "fremdes C-ECHO an unseren SCP" \
  "$(echoscu 127.0.0.1 "$BROKER_DICOM_PORT" -aec "$BROKER_AET" -aet "DCMTK_MOD" > /dev/null 2>&1 && echo 1 || echo 0)"

echo ""
echo "════════════════════════════════════════"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "INTEROP: alle Prüfungen bestanden (Fremdsoftware: DCMTK)"
  exit 0
else
  echo "INTEROP: fehlgeschlagen: ${FAILED[*]}"
  exit 1
fi
