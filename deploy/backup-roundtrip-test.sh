#!/usr/bin/env bash
# Round-Trip-Probe: Sichern → Daten zerstören → Wiederherstellen → prüfen.
# Läuft ausschließlich gegen den isolierten Test-Stack (.env.test).
set -euo pipefail
cd "$(dirname "$0")/.."

KEEP_STACK=0
[ "${1:-}" = "--keep-stack" ] && KEEP_STACK=1

COMPOSE=(docker compose --project-name mwl-test --env-file .env.test -f docker-compose.yml)
API="http://127.0.0.1:19081/api/v1"
BACKUP_DIR=/tmp/mwl-backup-roundtrip
MARKER="ACC-ROUNDTRIP-1"

info() { printf '==> %s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

info "Test-Stack starten"
"${COMPOSE[@]}" up -d >/dev/null 2>&1
for _ in $(seq 1 60); do
  curl -sf "$API/status" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "$API/status" >/dev/null || fail "Broker nicht erreichbar"
ok "Broker läuft"

info "Marker anlegen (lokaler Eintrag $MARKER)"
curl -sf -X POST "$API/local-items" -H 'Content-Type: application/json' \
  -H 'X-OE3-Roles: brokerWrite' \
  -d "{\"accession\":\"$MARKER\",\"sps_id\":\"1\",\"patient_id\":\"P-RT\",\"patient_name\":\"Runde^Rita\",\"modality\":\"CT\",\"station_aet\":\"CT_01\"}" \
  >/dev/null
count() { curl -s "$API/local-items" | grep -c "$MARKER" || true; }
[ "$(count)" -ge 1 ] || fail "Marker wurde nicht angelegt"
ok "Marker vorhanden"

info "Sicherung erstellen"
rm -rf "$BACKUP_DIR"
./deploy/backup.sh --dir "$BACKUP_DIR" --env-file .env.test > /tmp/roundtrip-backup.log 2>&1 \
  || { tail -5 /tmp/roundtrip-backup.log; fail "Sicherung fehlgeschlagen"; }
SNAPSHOT="$(ls -1dt "$BACKUP_DIR"/*/ | head -1)"
ok "Sicherung: $(basename "$SNAPSHOT")"

info "Daten zerstören (Marker löschen)"
ITEM_ID="$(curl -s "$API/local-items" | python3 -c "
import json,sys
for row in json.load(sys.stdin):
    if row['accession'] == '$MARKER':
        print(row['id']); break")"
[ -n "$ITEM_ID" ] || fail "Marker-ID nicht gefunden"
curl -sf -X DELETE "$API/local-items/$ITEM_ID" -H 'X-OE3-Roles: brokerWrite' >/dev/null
[ "$(count)" -eq 0 ] || fail "Marker ließ sich nicht löschen"
ok "Marker gelöscht (Datenbank enthält ihn nicht mehr)"

info "Wiederherstellen"
./deploy/backup.sh --restore "$SNAPSHOT" --env-file .env.test --yes \
  > /tmp/roundtrip-restore.log 2>&1 || { tail -8 /tmp/roundtrip-restore.log; fail "Wiederherstellung fehlgeschlagen"; }

info "Prüfen"
for _ in $(seq 1 30); do
  curl -sf "$API/status" >/dev/null 2>&1 && break
  sleep 2
done
[ "$(count)" -ge 1 ] || fail "Marker ist nach der Wiederherstellung nicht zurück"
ok "Marker ist wieder da — Round-Trip erfolgreich"

if [ "$KEEP_STACK" = 0 ]; then
  info "Aufräumen"
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1
  rm -rf "$BACKUP_DIR"
  ok "Test-Stack abgeräumt"
else
  rm -rf "$BACKUP_DIR"
  ok "Test-Stack bleibt stehen (--keep-stack)"
fi
echo "ROUND-TRIP OK"
