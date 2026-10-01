#!/usr/bin/env bash
# gap-audit.sh — alle Vertragsprüfungen an einer Stelle.
#
# Die Prüfungen gibt es (siehe unten), aber sie lagen über ein Dutzend Dateien
# verteilt: „haben wir dafür eine Analyse?" war eine Frage, die man durch Suchen
# beantworten musste. Dieses Script fährt sie der Reihe nach, nennt zu jeder den
# Umfang und druckt am Ende, was **nicht** geprüft wird — damit die Antwort auf
# diese Frage ein Kommando ist.
#
#   ./gap-audit.sh            # alles
#   ./gap-audit.sh --fast     # ohne die beiden vitest-Stages
#
# Rückgabewert: 0 = alle Stages grün, 1 = mindestens eine rot.
set -uo pipefail
cd "$(dirname "$0")"

FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

PY="mwl-broker/.venv/bin/pytest"
TESTS="mwl-broker/tests"
FE="orthanc-explorer-3-usable"
FAILED=0
PASSED=0

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
dim()  { printf '\033[2m%s\033[0m\n' "$*"; }

# stage "<Titel>" "<Was sie belegt>" <Befehl…>
stage() {
  local title="$1" scope="$2"; shift 2
  printf '\n── %s\n' "$title"
  dim "   $scope"
  local out
  if out="$(cd "$(dirname "$0")" && "$@" 2>&1)"; then
    printf '   \033[32mPASS\033[0m  %s\n' "$(printf '%s' "$out" | tail -1)"
    PASSED=$((PASSED + 1))
  else
    printf '   \033[31mFAIL\033[0m\n'
    printf '%s\n' "$out" | grep -E '^E |AssertionError|Error|✗|failed' | head -4 | sed 's/^/        /'
    FAILED=$((FAILED + 1))
  fi
}

py() { "$PY" -q --tb=line -p no:cacheprovider "$@"; }

bold "gap-audit — Vertrag UI ↔ API ↔ Backend"
dim "   $(date '+%Y-%m-%d %H:%M')  ·  Broker $(git rev-parse --short HEAD 2>/dev/null || echo '-')  ·  Fork $(git -C "$FE" describe --tags 2>/dev/null || echo '-')"

stage "1. Routen: UI → API (reverse)" \
      "jeder Pfad, den der typisierte Client ruft, existiert im Backend" \
      py "$TESTS/test_api_ui_contract.py" -k 'ui_call or allowlist'

stage "2. Routen: API → UI (forward)" \
      "jede Route ist aus der Oberfläche erreichbar oder begründet API-only" \
      py "$TESTS/test_api_ui_contract.py" -k 'reachable'

stage "3. Felder: Schreiben (forward)" \
      "jedes Feld eines *In/*Update-Schemas steht in einem Formular" \
      py "$TESTS/test_api_ui_contract.py" -k 'write_schema or node_forms'

stage "4. Felder: Antworten (forward)" \
      "jedes Antwortfeld ist in der UI sichtbar oder bewusst ausgenommen" \
      py "$TESTS/test_api_ui_contract.py" -k 'response_field or pairs_still_match'

stage "5. Felder: Client-Typ (reverse)" \
      "kein TS-Typ deklariert ein Feld, das das Backend nie sendet" \
      py "$TESTS/test_api_ui_contract.py" -k 'never_sends'

stage "6. Optionalität + Wertemengen" \
      "Pflichtfelder bleiben Pflicht, Wertemengen (Literal ↔ TS-Union) stimmen" \
      py "$TESTS/test_api_ui_contract.py" -k 'optional or value_sets or inline_kind'

stage "7. Settings: Startup vs. Betrieb" \
      "was nur beim Start gelesen wird, ist als restart_required markiert" \
      py "$TESTS/test_settings_startup.py"

stage "8. Settings: Deployment ↔ Container" \
      "dokumentierte ENV-Variable ist durchgereicht und wird wirklich gelesen" \
      py "$TESTS/test_deployment_config.py"

stage "9. Settings: Beschriftung" \
      "jede Einstellung hat Label und Beschreibung (en/de)" \
      py "$TESTS/test_settings_ui_labels.py"

stage "10. Protokoll: Entitäten + Aktionen" \
      "jede Entität und jede Aktion hat einen Text statt eines Codes" \
      py "$TESTS/test_audit_entity_labels.py" "$TESTS/test_audit_action_labels.py"

stage "11. Metriken: Alarmregeln ↔ Code" \
      "jede Regel verweist auf eine existierende Metrik und steht in der Doku" \
      py "$TESTS/test_monitoring_config.py"

stage "12. Betriebsdoku: Anker, Alarme, Hilfe" \
      "Runbook-Anker, Alarmnamen und Hilfeseiten passen zur Oberfläche" \
      py "$TESTS/test_support_docs.py"

stage "13. Conformance-Aussagen ↔ Code" \
      "die Zusagen in Conformance-/IHE-Statement decken sich mit der Umsetzung" \
      py "$TESTS/test_conformance_docs.py"

if [ "$FAST" = 0 ]; then
  stage "14. i18n: Keys (beide Richtungen)" \
        "kein toter Übersetzungsschlüssel, kein gerufener Key ohne Übersetzung" \
        bash -c "cd $FE && npx vitest run --silent=true src/features/broker/i18n-keys.test.ts"
fi

printf '\n'
bold "────────────────────────────────────────────────────────"
printf 'Stages grün: %d, rot: %d\n' "$PASSED" "$FAILED"

cat <<'NOTE'

Nicht geprüft (bewusst, mit Grund):
  · Query-Parameter und Request-Bodies — verglichen werden Pfade und Felder,
    nicht die Filter-/Body-Parameter einzelner Aufrufe
  · Fehlerantworten — die Struktur der `detail`-Meldungen gegen die Anzeige
  · Datums-/Zahlenformate — `ts: string` vs. `datetime` (die UI parst selbst)
  · Feature-Flags ↔ Deployment — ob die Oberfläche einen Schalter für eine
    Funktion zeigt, die dieser Stack nicht hat (Regel in agents.md, kein Test)
NOTE

[ "$FAILED" -eq 0 ]
