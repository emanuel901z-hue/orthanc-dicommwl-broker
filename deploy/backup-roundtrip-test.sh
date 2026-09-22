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
# nicht nur /status: die Datenbank muss auch antworten (Migrationen!)
for _ in $(seq 1 60); do
  curl -sf "$API/status" >/dev/null 2>&1 && curl -sf "$API/local-items" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "$API/local-items" >/dev/null || fail "Broker oder Datenbank antwortet nicht"
ok "Broker läuft (Status und Datenbank)"

info "Marker anlegen (lokaler Eintrag $MARKER)"
# einen Rest aus einem abgebrochenen Lauf zuerst entfernen
existing="$(curl -s "$API/local-items" | python3 -c "
import json,sys
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for row in rows:
    if row.get('accession') == '$MARKER':
        print(row['id']); break" || true)"
[ -n "$existing" ] && curl -sf -X DELETE "$API/local-items/$existing" \
  -H 'X-OE3-Roles: brokerWrite' >/dev/null || true

created="$(curl -s -X POST "$API/local-items" -H 'Content-Type: application/json' \
  -H 'X-OE3-Roles: brokerWrite' -w '\n%{http_code}' \
  -d "{\"accession\":\"$MARKER\",\"sps_id\":\"1\",\"patient_id\":\"P-RT\",\"patient_name\":\"Runde^Rita\",\"modality\":\"CT\",\"station_aet\":\"CT_01\"}")"
code="$(printf '%s' "$created" | tail -1)"
[ "$code" = "200" ] || [ "$code" = "201" ] || { printf '%s\n' "$created" | head -2 >&2; fail "Marker konnte nicht angelegt werden (HTTP $code)"; }
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
# Die Wiederherstellung startet den Broker neu — erst warten, bis er wieder
# vollständig antwortet (sonst sieht der nächste Schritt einen halbfertigen Dienst)
for _ in $(seq 1 60); do
  curl -sf "$API/status" >/dev/null 2>&1 && curl -sf "$API/local-items" >/dev/null 2>&1 && break
  sleep 2
done
[ "$(count)" -ge 1 ] || fail "Marker ist nach der Wiederherstellung nicht zurück"
ok "Marker ist wieder da — Round-Trip erfolgreich"

# Der Stack muss für den nächsten Schritt bereit sein (Health + Datenbank)
info "Stack bereit melden"
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:19081/healthz" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "http://127.0.0.1:19081/healthz" >/dev/null || fail "der Broker ist nach der Wiederherstellung nicht erreichbar"
ok "Broker antwortet wieder"

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
