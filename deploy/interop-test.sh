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
BROKER_TLS_PORT="${BROKER_TLS_PORT:-19083}"    # unser TLS-Listener (Test-Stack)
BROKER_AET="${BROKER_AET:-MWLBROKER}"
WLM_PORT="${WLM_PORT:-11116}"        # fremdes RIS   (wlmscpfs)
PACS_PORT="${PACS_PORT:-11117}"      # fremdes PACS  (dcmqrscp)
PACS_TLS_PORT="${PACS_TLS_PORT:-11119}"  # fremder TLS-Server (storescp +tls)
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
    pkill -x storescp 2>/dev/null
    docker rm -f interop-hl7rcv > /dev/null 2>&1
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

# ── Vorprüfung: die Fremdsoftware muss da sein — und wirklich DCMTK sein ──
# Achtung: `~/.local/bin` enthält **Python-Wrapper** mit denselben Namen
# (pynetdicom-CLI-Apps: findscu, storescu, echoscu, storescp) und liegt vor
# `/usr/bin` im PATH. Wer `findscu` aufruft, prüft dann unsere eigene
# Bibliothek statt Fremdsoftware — deshalb absolute Pfade und ein Nachweis.
DCMTK_BIN="${DCMTK_BIN:-/usr/bin}"
echo "── Fremdsoftware prüfen (DCMTK in $DCMTK_BIN) ──"
missing=()
for tool in wlmscpfs dcmqrscp findscu storescu echoscu dump2dcm dcmdump; do
  [ -x "$DCMTK_BIN/$tool" ] || missing+=("$tool")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "DCMTK fehlt in $DCMTK_BIN: ${missing[*]}"
  echo "Installieren mit: sudo apt install dcmtk"
  exit 2
fi
version=$("$DCMTK_BIN/echoscu" --version 2>&1 | head -1)
printf '%s' "$version" | grep -q "dcmtk" || {
  echo "Die Werkzeuge in $DCMTK_BIN sind nicht DCMTK: $version"
  exit 2
}
echo "   $version"
if command -v findscu > /dev/null 2>&1 && [ "$(command -v findscu)" != "$DCMTK_BIN/findscu" ]; then
  echo "   Hinweis: 'findscu' im PATH ist $(command -v findscu) — der Test nutzt $DCMTK_BIN/findscu"
fi

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
  "$DCMTK_BIN/dump2dcm" -g "$f" "$WORK/wlmdb/$WLM_AET/$(basename "$f" .dump).wl" > /dev/null 2>&1 && converted=$((converted + 1))
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
nohup "$DCMTK_BIN/wlmscpfs" -dfp "$WORK/wlmdb" "$WLM_PORT" > "$WORK/wlmscpfs.log" 2>&1 & disown
nohup "$DCMTK_BIN/dcmqrscp" --config "$WORK/dcmqrscp.cfg" "$PACS_PORT" > "$WORK/dcmqrscp.log" 2>&1 & disown
sleep 3
check "fremdes RIS antwortet (C-ECHO an $WLM_AET)" \
  "$("$DCMTK_BIN/echoscu" 127.0.0.1 "$WLM_PORT" -aec "$WLM_AET" -aet "$BROKER_AET" > /dev/null 2>&1 && echo 1 || echo 0)"
check "fremdes PACS antwortet (C-ECHO an $PACS_AET)" \
  "$("$DCMTK_BIN/echoscu" 127.0.0.1 "$PACS_PORT" -aec "$PACS_AET" -aet "$BROKER_AET" > /dev/null 2>&1 && echo 1 || echo 0)"

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
"$DCMTK_BIN/findscu" -W -k "0008,0050=" -k "0010,0010=" -k "0040,0100" \
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
"$DCMTK_BIN/storescu" 127.0.0.1 "$BROKER_DICOM_PORT" -aec "$BROKER_AET" -aet "DCMTK_MOD" \
  "$WORK/cstore.dcm" > "$WORK/cstore.out" 2>&1
store_ok=$?
check "die fremde Modalität bekommt den Store bestätigt" "$([ "$store_ok" -eq 0 ] && echo 1 || echo 0)" \
  "$(grep -oE 'Status: [0-9A-Fa-fx]+' "$WORK/cstore.out" | tail -1 || echo "exit=$store_ok")"

arrived=$(find "$WORK/pacs" -name "CT_*.dcm" -type f | wc -l)
check "das Bild liegt im fremden PACS" "$([ "$arrived" -ge 1 ] && echo 1 || echo 0)" "$arrived Datei(en)"
# unabhängig dekodiert: nicht mit pydicom, sondern mit DCMTK
if [ "$arrived" -ge 1 ]; then
  decoded=$("$DCMTK_BIN/dcmdump" "$(find "$WORK/pacs" -name "CT_*.dcm" -type f | head -1)" 2>/dev/null)
  check "der fremde Decoder liest die weitergeleiteten Daten" \
    "$(printf '%s' "$decoded" | grep -q "INTEROP-1" && echo 1 || echo 0)" \
    "$(printf '%s' "$decoded" | grep -E 'AccessionNumber|PatientID' | head -2 | tr -s ' ' | tr '\n' ' ' | cut -c1-70)"
fi

echo "── Unser Broker als SCP gegen die fremde Modalität (C-ECHO) ──"
check "fremdes C-ECHO an unseren SCP" \
  "$("$DCMTK_BIN/echoscu" 127.0.0.1 "$BROKER_DICOM_PORT" -aec "$BROKER_AET" -aet "DCMTK_MOD" > /dev/null 2>&1 && echo 1 || echo 0)"

echo "── Fremdsoftware 2: dcm4che (fremder MPPS-SCU + fremder HL7-Stack) ──"
# dcm4che (Java, Apache-2.0) hat, was DCMTK nicht hat: einen MPPS-**SCU**
# (`mppsscu`) und einen HL7-v2-Stack (`hl7snd`/`hl7rcv`) — plus echte fremde
# Beispielnachrichten (aus den alten IHE-MESA-Testdaten).
DCM4CHE_IMAGE="${DCM4CHE_IMAGE:-dcm4che/dcm4che-tools:5.33.1}"
NET=mwl-interop_default
if ! docker image inspect "$DCM4CHE_IMAGE" > /dev/null 2>&1; then
  echo "   übersprungen — Image fehlt:  docker pull $DCM4CHE_IMAGE"
else
  # fremder HL7-Empfänger für unsere Statusmeldungen (läuft im Stack-Netz)
  docker rm -f interop-hl7rcv > /dev/null 2>&1
  mkdir -p "$WORK/hl7"
  docker run -d --name interop-hl7rcv --network "$NET" -v "$WORK/hl7:/var/hl7" \
    "$DCM4CHE_IMAGE" hl7rcv -b 2576 --directory /var/hl7 > /dev/null
  sleep 3
  # Der MLLP-Listener ist standardmäßig aus (opt-in) und wird **beim Start**
  # aufgebaut: erst einschalten, dann neu starten — sonst bekommt der fremde
  # Sender "Connection refused".
  api /settings/hl7_mllp_enabled PUT '{"value":"true"}' > /dev/null
  $COMPOSE restart mwl-broker > /dev/null 2>&1
  for _ in $(seq 1 30); do
    curl -sf "$API/healthz" > /dev/null 2>&1 && break
    sleep 2
  done
  # unsere MPPS-Statusmeldung dorthin schicken (MLLP zum fremden Empfänger)
  api /settings/mpps_forward_enabled PUT '{"value":"true"}' > /dev/null
  api /settings/mpps_forward_transport PUT '{"value":"mllp"}' > /dev/null
  api /settings/mpps_forward_host PUT '{"value":"interop-hl7rcv"}' > /dev/null
  api /settings/mpps_forward_port PUT '{"value":"2576"}' > /dev/null

  # 1) fremder HL7-Sender → unser MLLP-Listener (fremde Auftragsnachricht)
  docker run --rm --network "$NET" "$DCM4CHE_IMAGE" \
    hl7snd -c mwl-broker:2575 \
    "/opt/dcm4che/etc/testdata/hl7/OMG^O19-GeneralClinicalOrder-Eyecare.hl7" \
    > "$WORK/hl7snd.out" 2>&1
  received=$(api '/hl7/messages?limit=20' | python3 -c "
import json,sys
for row in json.load(sys.stdin):
    if row.get('message_type','').startswith('OMG'):
        print(row.get('action','')); break
else:
    print('none')")
  check "unser MLLP-Listener nimmt eine fremde Auftragsnachricht an" \
    "$([ "$received" != "none" ] && [ "$received" != "rejected" ] && echo 1 || echo 0)" \
    "OMG^O19 → $received"

  # 1b) … und die *moderne* Auftragsnachricht (Imaging Order) ebenfalls
  docker run --rm --network "$NET" "$DCM4CHE_IMAGE" \
    hl7snd -c mwl-broker:2575 "/opt/dcm4che/etc/testdata/hl7/OMI^O23-ImagingOrder.hl7" \
    > "$WORK/hl7snd-omi.out" 2>&1
  imaging=$(api '/hl7/messages?limit=20' | python3 -c "
import json,sys
for row in json.load(sys.stdin):
    if row.get('message_type','').startswith('OMI'):
        print(row.get('action','')); break
else:
    print('none')")
  check "auch die Imaging Order (OMI^O23) wird angenommen" \
    "$([ "$imaging" != "none" ] && [ "$imaging" != "rejected" ] && echo 1 || echo 0)" \
    "OMI^O23 → $imaging"

  # 2) fremder HL7-Sender schickt einen Befund — der muss abgelehnt werden
  docker run --rm --network "$NET" "$DCM4CHE_IMAGE" \
    hl7snd -c mwl-broker:2575 "/opt/dcm4che/etc/testdata/hl7/ORU^R01-SR.hl7" \
    > "$WORK/hl7snd-oru.out" 2>&1
  rejected=$(api '/hl7/messages?limit=20' | python3 -c "
import json,sys
for row in json.load(sys.stdin):
    if row.get('message_type','').startswith('ORU'):
        print(row.get('action','')); break
else:
    print('none')")
  check "ein fremder Befund wird abgelehnt, nicht als Auftrag gelesen" \
    "$([ "$rejected" = "rejected" ] && echo 1 || echo 0)" "ORU^R01 → $rejected"

  # 3) fremde Modalität meldet einen Schritt (MPPS N-CREATE + N-SET)
  docker run --rm --network "$NET" "$DCM4CHE_IMAGE" \
    mppsscu -c "MWLBROKER@mwl-broker:11113" /opt/dcm4che/etc/testdata/dicom/MR01.dcm \
    > "$WORK/mppsscu.out" 2>&1
  steps=$(api /mpps | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null)
  check "unser MPPS-SCP nimmt einen fremden Schritt an" \
    "$([ "${steps:-0}" -ge 1 ] && echo 1 || echo 0)" "${steps:-0} Schritt(e)"

  # 4) und unsere Statusmeldung kommt bei der fremden Software an
  forwarded=0
  for _ in $(seq 1 20); do
    forwarded=$(find "$WORK/hl7" -type f 2>/dev/null | wc -l)
    [ "$forwarded" -ge 1 ] && break
    sleep 1
  done
  check "unsere MPPS-Statusmeldung erreicht den fremden HL7-Empfänger" \
    "$([ "$forwarded" -ge 1 ] && echo 1 || echo 0)" "$forwarded Datei(en)"
  if [ "$forwarded" -ge 1 ]; then
    # der fremde Empfänger legt je Nachrichtentyp ab — und wir lesen mit seinen Augen
    type=$(tr -d '\r' < "$(find "$WORK/hl7" -type f | head -1)" | head -1 | cut -d'|' -f9)
    check "die Statusmeldung ist eine gültige HL7-Nachricht" \
      "$(printf '%s' "$type" | grep -q '\^' && echo 1 || echo 0)" "MSH-9: $type"
  fi
  docker rm -f interop-hl7rcv > /dev/null 2>&1
fi

echo "── Fremdsoftware 4: TLS gegen einen fremden TLS-Stack (DCMTK) ──"
# Unser TLS/mTLS war bisher pydicom-gegen-pydicom geprüft. Hier steht auf der
# anderen Seite eine fremde TLS-Implementierung — in beide Richtungen.
if ! command -v openssl > /dev/null 2>&1; then
  echo "   übersprungen — openssl fehlt"
else
  # eigener TLS-Listener: Zertifikat erzeugen, die Pfade eintragen, einschalten,
  # neu starten (der Listener wird beim Hochfahren aufgebaut).
  # Hinweis: `POST /tls/self-signed` schreibt die Dateien, trägt sie aber *nicht*
  # in die Einstellungen ein — ohne die zwei Pfade bleibt der Listener
  # "not configured". Die Antwort liefert das Zertifikat direkt mit.
  generated=$(api /tls/self-signed POST \
    '{"common_name":"mwl-broker.interop.local","days":30,"san":["127.0.0.1","localhost"]}')
  printf '%s' "$generated" | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['certificate_pem'])" > "$WORK/broker-cert.pem" 2>/dev/null
  cert_file=$(printf '%s' "$generated" | python3 -c "import json,sys; print(json.load(sys.stdin)['certificate_path'])" 2>/dev/null)
  key_file=$(printf '%s' "$generated" | python3 -c "import json,sys; print(json.load(sys.stdin)['key_path'])" 2>/dev/null)
  api /settings/tls_inbound_cert_file PUT "{\"value\":\"$cert_file\"}" > /dev/null
  api /settings/tls_inbound_key_file PUT "{\"value\":\"$key_file\"}" > /dev/null
  api /settings/tls_inbound_enabled PUT '{"value":"true"}' > /dev/null
  $COMPOSE restart mwl-broker > /dev/null 2>&1
  for _ in $(seq 1 30); do
    curl -sf "$API/healthz" > /dev/null 2>&1 && break
    sleep 2
  done
  check "Zertifikat für die Fremdseite bereit" \
    "$([ -s "$WORK/broker-cert.pem" ] && echo 1 || echo 0)" \
    "$(wc -c < "$WORK/broker-cert.pem" 2>/dev/null | tr -d ' ') Bytes"

  # a) fremder TLS-Client → unser TLS-Listener.
  # Der veröffentlichte Port ist sofort offen (docker-proxy) — also nicht den
  # Port prüfen, sondern den Handshake, und bis dahin erneut versuchen.
  tls_ready=0
  tls_error=""
  for _ in $(seq 1 30); do
    tls_error=$("$DCMTK_BIN/echoscu" +tla +cf "$WORK/broker-cert.pem" 127.0.0.1 "$BROKER_TLS_PORT" \
      -aec "$BROKER_AET" 2>&1 | grep -E "^F:|^E:" | head -1)
    [ -z "$tls_error" ] && { tls_ready=1; break; }
    sleep 2
  done
  check "fremdes C-ECHO über TLS an unseren Listener" "$tls_ready" \
    "${tls_error:-Verbunden, kein Fehler}"
  # ein Bild über TLS schicken (der Modalitätenpfad; DCMTK's `findscu` hat in
  # diesem Build keine TLS-Optionen, `storescu` und `echoscu` haben sie)
  "$DCMTK_BIN/storescu" +tla -ic 127.0.0.1 "$BROKER_TLS_PORT" "$WORK/cstore.dcm" \
    -aec "$BROKER_AET" -aet DCMTK_TLS > "$WORK/cstore-intls.out" 2>&1
  tls_store_ok=$?
  stored=$(api '/logs/stores?limit=5' | python3 -c "
import json,sys
rows = json.load(sys.stdin)
print(sum(1 for r in rows if r.get('status') == 'success'))" 2>/dev/null)
  check "fremde Modalität schickt ein Bild über TLS" \
    "$([ "$tls_store_ok" -eq 0 ] && [ "${stored:-0}" -ge 1 ] && echo 1 || echo 0)" \
    "exit=$tls_store_ok, zugestellt=${stored:-0}"

  # b) unser TLS-Client → fremder TLS-Server, als **mTLS**: DCMTK's `storescp
  #    +tls` verlangt ein Client-Zertifikat ("peer did not return a certificate"),
  #    und DCMTK muss es kennen. Genau das ist der Fall aus dem echten Haus.
  openssl req -x509 -newkey rsa:2048 -nodes -keyout "$WORK/dcmtk-key.pem" \
    -out "$WORK/dcmtk-cert.pem" -days 30 -subj "/CN=dcmtk-tls-interop" > /dev/null 2>&1
  openssl req -x509 -newkey rsa:2048 -nodes -keyout "$WORK/client-key.pem" \
    -out "$WORK/client-cert.pem" -days 30 -subj "/CN=mwl-broker-client" > /dev/null 2>&1
  mkdir -p "$WORK/pacs-tls"
  # DCMTK kennt unser Client-Zertifikat (CA-Liste der Fremdseite)
  nohup "$DCMTK_BIN/storescp" +tls "$WORK/dcmtk-key.pem" "$WORK/dcmtk-cert.pem" \
    +cf "$WORK/client-cert.pem" -od "$WORK/pacs-tls" "$PACS_TLS_PORT" \
    > "$WORK/storescp-tls.log" 2>&1 & disown
  tls_server=0
  for _ in $(seq 1 10); do
    (exec 3<>/dev/tcp/127.0.0.1/"$PACS_TLS_PORT") 2>/dev/null && { tls_server=1; break; }
    sleep 1
  done
  check "fremder TLS-Server lauscht ("$DCMTK_BIN/storescp" +tls)" "$tls_server" \
    "$(head -1 "$WORK/storescp-tls.log" 2>/dev/null | cut -c1-70)"
  # unser Client-Zertifikat in den Broker laden und als Ausgangsidentität setzen
  uploaded=$(python3 - "$WORK" "$API" <<'PYU'
import json, sys, urllib.request
work, api = sys.argv[1], sys.argv[2]
body = {
    "certificate_pem": open(f"{work}/client-cert.pem").read(),
    "key_pem": open(f"{work}/client-key.pem").read(),
    "ca_pem": open(f"{work}/dcmtk-cert.pem").read(),   # wir vertrauen der Fremdseite
    "filename": "interop-client",
}
request = urllib.request.Request(f"{api}/api/v1/tls/upload", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=15) as response:
    print(json.dumps(json.loads(response.read())))
PYU
)
  client_cert=$(printf '%s' "$uploaded" | python3 -c "import json,sys; print(json.load(sys.stdin).get('certificate_path',''))" 2>/dev/null)
  client_key=$(printf '%s' "$uploaded" | python3 -c "import json,sys; print(json.load(sys.stdin).get('key_path',''))" 2>/dev/null)
  api /settings/tls_outbound_client_cert_file PUT "{\"value\":\"$client_cert\"}" > /dev/null
  api /settings/tls_outbound_client_key_file PUT "{\"value\":\"$client_key\"}" > /dev/null
  tls_target=$(api /targets POST \
    "{\"name\":\"dcmtk-tls\",\"aet\":\"DCMTK_TLS\",\"host\":\"$HOST_FOR_CONTAINER\",\"port\":$PACS_TLS_PORT,\"calling_aet\":\"$BROKER_AET\",\"is_default\":false,\"enabled\":true,\"tls\":true,\"tls_verify\":false}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" 2>/dev/null)
  api /rules POST "{\"source_id\":$source_id,\"target_id\":$tls_target,\"priority\":0}" > /dev/null
  "$DCMTK_BIN/storescu" 127.0.0.1 "$BROKER_DICOM_PORT" -aec "$BROKER_AET" -aet "DCMTK_MOD" \
    "$WORK/cstore.dcm" > "$WORK/cstore-tls.out" 2>&1
  sleep 3
  tls_arrived=$(find "$WORK/pacs-tls" -type f 2>/dev/null | wc -l)
  check "unser mTLS-Client liefert an einen fremden TLS-Server" \
    "$([ "${tls_arrived:-0}" -ge 1 ] && echo 1 || echo 0)" \
    "${tls_arrived:-0} Datei(en); Fremdseite: $(grep -oE 'TLS error: [a-z ]+' "$WORK/storescp-tls.log" 2>/dev/null | head -1)"
  pkill -x storescp 2>/dev/null
fi

echo ""
echo "════════════════════════════════════════"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "INTEROP: alle Prüfungen bestanden (Fremdsoftware: DCMTK)"
  exit 0
else
  echo "INTEROP: fehlgeschlagen: ${FAILED[*]}"
  exit 1
fi
