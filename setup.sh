#!/usr/bin/env bash
# setup.sh — geführte Produktiv-Inbetriebnahme des MWL-Broker-Stacks.
#
# Das Script führt Schritt für Schritt durch alles, was vor dem ersten echten
# Betrieb erledigt sein muss, und fängt dabei die typischen Fehler ab:
#
#   1. Docker/Compose prüfen            (installieren auf Wunsch)
#   2. .env anlegen/prüfen              (fehlende, schwache, falsche Werte)
#   3. Host-Ports prüfen                (Kollisionen, Doppelbelegung, freie Vorschläge)
#   4. Stack bauen und starten          (ohne Demo-Services!)
#   5. Broker konfigurieren             (RBAC, AET-Whitelist, TLS, Alerting,
#                                        ATNA, MLLP, Aufbewahrung)
#   6. Prüfen und abschließen           (Health, Tests, Restliste zum Abhaken)
#
# Sicherheitsnetz für unbedarfte Bedienung:
#   • jede Änderung wird vorher angezeigt ("alt → neu") und bestätigt
#   • die .env wird vor jeder Änderung gesichert (.env.backup-<Zeitstempel>)
#   • Passwörter werden nie angezeigt, nur maskiert
#   • jede Eingabe wird geprüft und bei Fehlern erneut abgefragt (nie Absturz)
#   • Enter übernimmt den Vorschlag, "s" überspringt, "q" beendet ohne Änderung
#   • keine zerstörenden Aktionen (kein down -v, kein Löschen von Daten)
#
# Aufrufe:
#   ./setup.sh                  geführte Einrichtung
#   ./setup.sh --check          nur prüfen und berichten, nichts ändern
#   ./setup.sh --dry-run        zeigen, was passieren würde
#   ./setup.sh --yes            alle Vorschläge annehmen (Automatisierung)
#   ./setup.sh --self-test      nur die Prüffunktionen testen (CI, ohne Docker)
#   ./setup.sh --env-file F     andere Umgebungsdatei (z.B. .env.test)
set -euo pipefail
cd "$(dirname "$0")"

# ── Optionen ────────────────────────────────────────────────────────────────
CHECK_ONLY=0
DRY_RUN=0
ASSUME_YES=0
SELF_TEST=0
SKIP_STACK=0
ENV_FILE=".env"
INSTALL_DOCKER=0
NO_COLOR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --self-test) SELF_TEST=1 ;;
    --skip-stack) SKIP_STACK=1 ;;
    --install-docker) INSTALL_DOCKER=1 ;;
    --env-file)
      ENV_FILE="${2:-}"
      [ -n "$ENV_FILE" ] || { echo "--env-file braucht einen Pfad" >&2; exit 2; }
      shift ;;
    --no-color) NO_COLOR=1 ;;
    -h|--help) sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unbekannte Option: $1 (--help zeigt alles)" >&2; exit 2 ;;
  esac
  shift
done

# Ist ein Terminal vorhanden? Ohne Terminal kann nicht gefragt werden.
INTERACTIVE=0
{ [ -t 0 ] || [ -r /dev/tty ]; } && INTERACTIVE=1
if [ "$ASSUME_YES" = 0 ] && [ "$CHECK_ONLY" = 0 ] && [ "$DRY_RUN" = 0 ] && [ "$INTERACTIVE" = 0 ]; then
  printf 'FAIL: Keine interaktive Sitzung (kein Terminal verfügbar).\n' >&2
  printf '      Entweder in einem Terminal ausführen oder:\n' >&2
  printf '        ./setup.sh --yes        (nimmt alle Vorschläge an)\n' >&2
  printf '        ./setup.sh --check      (nur prüfen, ändert nichts)\n' >&2
  exit 2
fi

if [ ! -t 1 ] || [ "$NO_COLOR" = 1 ]; then
  C_RESET=""; C_STEP=""; C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""
else
  C_RESET=$'\033[0m'; C_STEP=$'\033[1;34m'; C_OK=$'\033[1;32m'
  C_WARN=$'\033[1;33m'; C_ERR=$'\033[1;31m'; C_DIM=$'\033[2m'
fi

step() { printf '\n%s==> %s%s\n' "$C_STEP" "$*" "$C_RESET"; }
ok()   { printf '%s  ✓%s %s\n' "$C_OK" "$C_RESET" "$*"; }
warn() { printf '%sWARN:%s %s\n' "$C_WARN" "$C_RESET" "$*" >&2; }
fail() { printf '%sFAIL:%s %s\n' "$C_ERR" "$C_RESET" "$*" >&2; exit 1; }
note() { printf '%s      %s%s\n' "$C_DIM" "$*" "$C_RESET"; }
hr()   { printf '%s%s%s\n' "$C_DIM" "────────────────────────────────────────────────────────────────────────" "$C_RESET"; }

# Zähler für die Abschlussbilanz
CHANGED=0
PROBLEMS=0
MANUAL=()

# ── reine Prüffunktionen (auch vom --self-test genutzt) ─────────────────────
is_int()          { [[ "${1:-}" =~ ^[0-9]+$ ]]; }
in_range()        { is_int "${1:-}" && [ "$1" -ge "$2" ] && [ "$1" -le "$3" ]; }
valid_aet()       { [[ "${1:-}" =~ ^[A-Z0-9_]{1,16}$ ]]; }
valid_host()      { [[ "${1:-}" =~ ^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$ ]]; }
valid_ip()        { [[ "${1:-}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }
valid_url()       { [[ "${1:-}" =~ ^https?://[^[:space:]]+$ ]]; }
valid_path()      { [[ "${1:-}" =~ ^/[A-Za-z0-9._/-]+$ ]]; }
valid_mail()      { [[ "${1:-}" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; }
mask()            { local v="${1:-}"; [ -z "$v" ] && { echo "(leer)"; return; }; \
                    [ "${#v}" -le 4 ] && { echo "••••"; return; }; echo "${v:0:2}••••${v: -2}"; }
weak_secret()     { case "$(printf '%s' "${1:-}" | tr 'A-Z' 'a-z')" in \
                      ""|dev|devdev|password|passwort|changeme|change-me|secret|geheim|test|admin|123456|12345678|qwerty|letmein) return 0 ;; \
                    esac; [ "${#1}" -lt 12 ] && return 0; return 1; }
gen_password()    { # python3 (immer vorhanden) oder /dev/urandom; kein SIGPIPE
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))'
  else
    LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 24 || true
  fi
}
suggest_port()    { local p="$1" tries=0; while [ $tries -lt 200 ]; do \
                      port_in_use "$p" || { echo "$p"; return 0; }; p=$((p + 1)); tries=$((tries + 1)); done; echo "$1"; }
port_in_use()     { ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${1}$"; }

# ── Eingabe-Helfer (DAU-sicher: prüfen, wiederholen, nie abstürzen) ─────────
ask() {   # ask "Frage" "Vorschlag" "Validierungsfunktion"
  local question="$1" suggestion="${2:-}" validator="${3:-}"
  local answer=""
  if [ "$ASSUME_YES" = 1 ]; then echo "$suggestion"; return 0; fi
  while true; do
    if [ -n "$suggestion" ]; then
      printf '%s [%s]: ' "$question" "$suggestion"
    else
      printf '%s: ' "$question"
    fi
    read -r answer <"${TTY_IN:-/dev/tty}" || return 1
    [ -z "$answer" ] && answer="$suggestion"
    case "$answer" in q|Q) return 2 ;; esac
    if [ -z "$validator" ] || "$validator" "$answer"; then echo "$answer"; return 0; fi
    printf '%s  Ungültig.%s Bitte erneut (Enter = Vorschlag, q = abbrechen).\n' "$C_ERR" "$C_RESET" >&2
  done
}

confirm() {  # confirm "Frage" -> 0/1
  [ "$ASSUME_YES" = 1 ] && return 0
  local answer=""
  printf '%s [j/N]: ' "$1"
  read -r answer <"${TTY_IN:-/dev/tty}" || return 1
  case "$answer" in j|J|y|Y) return 0 ;; *) return 1 ;; esac
}

choose() {   # choose "Frage" "1:Text" "2:Text" ... -> Nummer
  local question="$1"; shift
  [ "$ASSUME_YES" = 1 ] && { echo 1; return 0; }
  printf '%s\n' "$question"
  local i=1
  for option in "$@"; do printf '   %d) %s\n' "$i" "$option"; i=$((i + 1)); done
  local answer=""
  while true; do
    printf 'Auswahl [1]: '
    read -r answer <"${TTY_IN:-/dev/tty}" || return 1
    [ -z "$answer" ] && answer=1
    if is_int "$answer" && [ "$answer" -ge 1 ] && [ "$answer" -le "$#" ]; then echo "$answer"; return 0; fi
    printf '%s  Bitte eine Zahl zwischen 1 und %d.%s\n' "$C_ERR" "$#" "$C_RESET" >&2
  done
}

# ── .env lesen/schreiben ───────────────────────────────────────────────────
TTY_IN="/dev/tty"
[ -r /dev/tty ] || TTY_IN="/dev/stdin"

declare -A ENV=()
load_env() {
  local line key value
  ENV=()
  [ -f "$ENV_FILE" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*|*=*) ;; *) continue ;; esac
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"; value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    value="${value#"${value%%[![:space:]]*}"}"; value="${value%"${value##*[![:space:]]}"}"
    case "$value" in \"*\") value="${value#\"}"; value="${value%\"}" ;; \'*\') value="${value#\'}"; value="${value%\'}" ;; esac
    [ -n "$key" ] && ENV["$key"]="$value"
  done < "$ENV_FILE"
}
env_get() { printf '%s' "${ENV[${1:-}]:-}"; }

env_set() {  # env_set KEY VALUE — atomar, mit Backup, Reihenfolge bleibt
  local key="$1" value="$2"
  ENV["$key"]="$value"
  if [ "$DRY_RUN" = 1 ]; then note "[dry-run] $key=$value"; return 0; fi
  local tmp; tmp="$(mktemp)"
  local found=0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "$key"=*) printf '%s=%s\n' "$key" "$value" >>"$tmp"; found=1 ;;
      *) printf '%s\n' "$line" >>"$tmp" ;;
    esac
  done < "$ENV_FILE"
  [ "$found" = 1 ] || printf '%s=%s\n' "$key" "$value" >>"$tmp"
  cat "$tmp" >"$ENV_FILE"      # gleiche Datei/Rechte behalten
  rm -f "$tmp"
}

backup_env() {
  [ -f "$ENV_FILE" ] || return 0
  local target="${ENV_FILE}.backup-$(date +%Y%m%d-%H%M%S)"
  cp "$ENV_FILE" "$target"
  chmod 600 "$target" 2>/dev/null || true
  BACKUP_FILE="$target"
  ok "Sicherung angelegt: $target"
}

CHANGE_LOG="$(mktemp)"
cleanup() {
  rm -f "$CHANGE_LOG"
  if [ "${INTERRUPTED:-0}" = 1 ]; then
    printf '\n%sAbgebrochen.%s\n' "$C_WARN" "$C_RESET" >&2
    [ -n "${BACKUP_FILE:-}" ] && printf '   Die vorherige %s liegt unter: %s\n' "$ENV_FILE" "$BACKUP_FILE" >&2
    printf '   Änderungen bis hierher sind bereits geschrieben (siehe oben).\n' >&2
  fi
}
trap 'INTERRUPTED=1; cleanup; exit 130' INT TERM
trap cleanup EXIT

# ── Selbsttest der Prüffunktionen (CI-fähig, ohne Docker) ──────────────────
self_test() {
  local failed=0
  check() { # check "Name" Bedingung-Ergebnis erwartet
    if [ "$2" = "$3" ]; then printf '  ok   %s\n' "$1"; else printf '  FAIL %s (%s ≠ %s)\n' "$1" "$2" "$3"; failed=1; fi
  }
  check "is_int 8081"        "$(is_int 8081 && echo ja || echo nein)" "ja"
  check "is_int 8x"          "$(is_int 8x && echo ja || echo nein)" "nein"
  check "in_range 5..60"     "$(in_range 30 5 60 && echo ja || echo nein)" "ja"
  check "in_range 0..60"     "$(in_range 0 5 60 && echo ja || echo nein)" "nein"
  check "valid_aet MWLBROKER" "$(valid_aet MWLBROKER && echo ja || echo nein)" "ja"
  check "valid_aet klein"     "$(valid_aet mwlb && echo ja || echo nein)" "nein"
  check "valid_host ip"       "$(valid_host 10.0.1.47 && echo ja || echo nein)" "ja"
  check "valid_host leer"     "$(valid_host '' && echo ja || echo nein)" "nein"
  check "valid_url https"     "$(valid_url https://hooks.example/x && echo ja || echo nein)" "ja"
  check "valid_url ohne schema" "$(valid_url hooks.example && echo ja || echo nein)" "nein"
  check "valid_path abs"      "$(valid_path /var/lib/mwl-broker/spool && echo ja || echo nein)" "ja"
  check "valid_path relativ"  "$(valid_path var/spool && echo ja || echo nein)" "nein"
  check "valid_mail"          "$(valid_mail a@b.de && echo ja || echo nein)" "ja"
  check "weak dev"            "$(weak_secret dev && echo schwach || echo stark)" "schwach"
  check "weak kurz"           "$(weak_secret kurz12 && echo schwach || echo stark)" "schwach"
  check "stark"               "$(weak_secret 'Xq7-vollkommen-egal-2026' && echo schwach || echo stark)" "stark"
  check "mask kurz"           "$(mask ab)" "••••"
  check "mask leer"           "$(mask '')" "(leer)"
  check "mask lang"           "$(mask abcdefgh)" "ab••••gh"
  local pw; pw="$(gen_password)"
  check "gen_password 24"     "${#pw}" "24"
  check "gen_password nicht schwach" "$(weak_secret "$pw" && echo schwach || echo stark)" "stark"
  [ "$failed" = 0 ] && { echo "selbsttest: alle Prüfungen ok"; return 0; }
  echo "selbsttest: FEHLGESCHLAGEN"; return 1
}
if [ "$SELF_TEST" = 1 ]; then self_test; exit $?; fi

# ── Start ──────────────────────────────────────────────────────────────────
hr
printf '%sMWL-Broker — Produktiv-Inbetriebnahme%s\n' "$C_STEP" "$C_RESET"
hr
note "Dieses Script prüft und füllt die Konfiguration, startet den Stack und"
note "richtet die Betriebseinstellungen ein. Es ändert nichts ohne Rückfrage."
[ "$CHECK_ONLY" = 1 ] && note "Modus: nur prüfen (--check) — es wird nichts geändert."
[ "$DRY_RUN" = 1 ] && note "Modus: Probelauf (--dry-run) — es wird nichts geändert."
[ "$ASSUME_YES" = 1 ] && note "Modus: alle Vorschläge werden angenommen (--yes)."

# ══ 1. Docker ══════════════════════════════════════════════════════════════
step "1/6  Docker prüfen"
if ! command -v docker >/dev/null 2>&1; then
  if [ "$INSTALL_DOCKER" = 1 ] && [ "$CHECK_ONLY" = 0 ] && [ "$DRY_RUN" = 0 ]; then
    warn "Docker fehlt — Installation über get.docker.com"
    sh -c 'curl -fsSL https://get.docker.com | sh'
  else
    fail "Docker ist nicht installiert.
      Entweder ./setup.sh --install-docker  oder manuell:
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker \$USER   # danach neu einloggen"
  fi
fi
docker compose version >/dev/null 2>&1 || fail "docker compose (Plugin) fehlt — Paket docker-compose-plugin installieren"
docker info >/dev/null 2>&1 || fail "Kein Zugriff auf den Docker-Daemon. Einmalig:
      sudo usermod -aG docker \$USER && newgrp docker"
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) mit Compose"

# ══ 2. .env ════════════════════════════════════════════════════════════════
step "2/6  Konfiguration ($ENV_FILE)"
if [ ! -f "$ENV_FILE" ]; then
  if [ -f .env.example ] && [ "$ENV_FILE" = ".env" ]; then
    [ "$DRY_RUN" = 0 ] && cp .env.example .env
    ok ".env aus .env.example angelegt"
  else
    fail "$ENV_FILE fehlt — Vorlage kopieren: cp .env.example $ENV_FILE"
  fi
fi
chmod 600 "$ENV_FILE" 2>/dev/null || true
load_env

# Ist die Datei versehentlich im Git? (Secrets!)
if git rev-parse --git-dir >/dev/null 2>&1 && [ "$ENV_FILE" = ".env" ]; then
  if git check-ignore -q .env 2>/dev/null; then ok ".env ist von Git ignoriert"
  else warn ".env ist NICHT von .gitignore abgedeckt — bitte prüfen, sie enthält Passwörter"; MANUAL+=(".env in .gitignore aufnehmen"); fi
fi

# Sammeln, was nicht in Ordnung ist
ISSUES=()        # muss korrigiert werden (fragt nach)
OPTIONAL=()      # fehlt, hat aber einen Standardwert im Compose-File (nur Hinweis)
issue()     { ISSUES+=("$1|$2|$3|$4"); }     # KEY|IST|WARUM|VORSCHLAG
note_opt()  { OPTIONAL+=("$1|$2"); }         # KEY|STANDARDWERT

# "optional" = der Wert hat im Compose-File/Beispiel einen Standard und darf fehlen
check_value() {  # check_value KEY "Warum" "Vorschlag" "Validator" [optional]
  local key="$1" why="$2" suggestion="$3" validator="${4:-}" optional="${5:-}"
  local current; current="$(env_get "$key")"
  if [ -z "$current" ]; then
    if [ "$optional" = "optional" ]; then note_opt "$key" "$suggestion"; else issue "$key" "(leer)" "$why" "$suggestion"; fi
    return
  fi
  if [ -n "$validator" ] && ! "$validator" "$current"; then issue "$key" "$current" "$why" "$suggestion"; fi
}

check_value COMPOSE_PROJECT_NAME "Projektname für Docker (muss eindeutig sein)" "mwl-broker" valid_host
check_value POSTGRES_USER "Datenbank-Benutzer" "mwlbroker" valid_host
# Passwort: leer, schwach oder Dev-Wert
if weak_secret "$(env_get POSTGRES_PASSWORD)"; then
  issue POSTGRES_PASSWORD "$(mask "$(env_get POSTGRES_PASSWORD)")" \
    "Das Datenbank-Passwort ist ein Standard-/Dev-Wert oder zu kurz" "$(gen_password)"
fi
check_value ORTHANC_AET "AET des Orthanc (1–16 Zeichen, A–Z 0–9 _)" "ORTHANC" valid_aet
check_value BROKER_AET "AET des Brokers — die Modalitäten adressieren diesen Namen" "MWLBROKER" valid_aet
check_value ORTHANC_HTTP_BIND "Bind-Adresse der Orthanc-REST-Schnittstelle (127.0.0.1 = nur lokal)" "127.0.0.1" valid_host
check_value BROKER_API_BIND "Bind-Adresse der Broker-API (127.0.0.1 = nur lokal)" "127.0.0.1" valid_host
check_value BROKER_SPOOL_DIR "Verzeichnis für gepufferte Bilder (im Container)" "/var/lib/mwl-broker/spool" valid_path optional
for pair in "ORTHANC_DICOM_PORT:1:65535" "ORTHANC_HTTP_PORT:1:65535" "BROKER_DICOM_PORT:1:65535" \
            "BROKER_API_PORT:1:65535" "OE3_PORT:1:65535" "BROKER_ECHO_INTERVAL_S:5:3600" \
            "BROKER_UPSTREAM_TIMEOUT_S:1:600"; do
  key="${pair%%:*}"; rest="${pair#*:}"; lo="${rest%%:*}"; hi="${rest#*:}"
  current="$(env_get "$key")"
  if [ -z "$current" ]; then issue "$key" "(leer)" "Pflichtwert fehlt" "$lo"
  elif ! in_range "$current" "$lo" "$hi"; then issue "$key" "$current" "Muss zwischen $lo und $hi liegen" "$lo"; fi
done

# Doppelbelegungen innerhalb der .env
declare -A SEEN_PORT=()
for key in ORTHANC_DICOM_PORT ORTHANC_HTTP_PORT BROKER_DICOM_PORT BROKER_API_PORT OE3_PORT; do
  p="$(env_get "$key")"
  [ -z "$p" ] && continue
  if [ -n "${SEEN_PORT[$p]:-}" ]; then
    issue "$key" "$p" "Port $p ist in der .env schon für ${SEEN_PORT[$p]} vergeben" "$(suggest_port $((p + 1)))"
  else SEEN_PORT[$p]="$key"; fi
done

if [ "${#OPTIONAL[@]}" -gt 0 ]; then
  printf '\n  Hinweis: %d Wert(e) sind nicht gesetzt und nutzen den Standard aus dem Compose-File:\n' "${#OPTIONAL[@]}"
  for entry in "${OPTIONAL[@]}"; do IFS='|' read -r key value <<<"$entry"; printf '   • %s = %s\n' "$key" "$value"; done
fi

if [ "${#ISSUES[@]}" -eq 0 ]; then
  ok "Alle Pflichtwerte sind gesetzt und plausibel"
else
  printf '\n%s  %d Punkt(e) brauchen Aufmerksamkeit:%s\n' "$C_WARN" "${#ISSUES[@]}" "$C_RESET"
  for entry in "${ISSUES[@]}"; do
    IFS='|' read -r key current why suggestion <<<"$entry"
    printf '   • %s: %s\n     %s\n     Vorschlag: %s\n' "$key" "$current" "$why" "$suggestion"
  done
  PROBLEMS="${#ISSUES[@]}"

  if [ "$CHECK_ONLY" = 1 ]; then
    printf '\n   (--check: es wird nichts geändert)\n'
  else
    [ "$DRY_RUN" = 0 ] && backup_env
    for entry in "${ISSUES[@]}"; do
      IFS='|' read -r key current why suggestion <<<"$entry"
      printf '\n%s%s%s\n   jetzt: %s\n   %s\n' "$C_STEP" "$key" "$C_RESET" "$current" "$why"
      answer="$(ask "Neuer Wert" "$suggestion")" || { warn "Übersprungen (q)"; continue; }
      [ -z "$answer" ] && continue
      if [ "$answer" != "$suggestion" ] && [ "$key" = "POSTGRES_PASSWORD" ] && weak_secret "$answer"; then
        warn "Dieses Passwort ist zu kurz oder ein Standardwert — bitte ein längeres verwenden."
        answer="$(ask "Neuer Wert" "$suggestion")" || continue
      fi
      env_set "$key" "$answer"
      if [ "$key" = "POSTGRES_PASSWORD" ]; then
        printf '%s  ✓ gesetzt:%s %s\n' "$C_OK" "$C_RESET" "$(mask "$answer")"
      else
        printf '%s  ✓ gesetzt:%s %s\n' "$C_OK" "$C_RESET" "$answer"
      fi
      CHANGED=$((CHANGED + 1))
    done
    # neu laden, damit spätere Schritte die neuen Werte sehen
    load_env
  fi
fi

# ══ 3. Ports ═══════════════════════════════════════════════════════════════
step "3/6  Host-Ports prüfen"
declare -A PORT_LABEL=(
  ["$(env_get ORTHANC_HTTP_PORT)"]="Orthanc REST"
  ["$(env_get ORTHANC_DICOM_PORT)"]="Orthanc DICOM"
  ["$(env_get BROKER_API_PORT)"]="Broker API"
  ["$(env_get BROKER_DICOM_PORT)"]="Broker DICOM (Modalitäten)"
  ["$(env_get OE3_PORT)"]="OE3-Oberfläche"
)
collisions=0
for port in "${!PORT_LABEL[@]}"; do
  [ -z "$port" ] && continue
  if port_in_use "$port"; then
    if docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":${port}->"; then
      ok "Port $port gehört bereits zu diesem Stack (${PORT_LABEL[$port]})"
    else
      warn "Port $port (${PORT_LABEL[$port]}) ist von einem anderen Prozess belegt"
      note "In $ENV_FILE ändern, z.B. auf $(suggest_port "$port")"
      collisions=$((collisions + 1))
    fi
  else
    ok "Port $port frei (${PORT_LABEL[$port]})"
  fi
done
[ "$collisions" -gt 0 ] && warn "$collisions Port-Konflikt(e) — docker compose bricht beim Start ab, wenn sie bleiben"
# DICOM-Ports müssen von den Modalitäten erreichbar sein: Bind-Adresse prüfen
if [ "$(env_get ORTHANC_HTTP_BIND)" = "0.0.0.0" ] || [ "$(env_get BROKER_API_BIND)" = "0.0.0.0" ]; then
  warn "Orthanc-REST oder Broker-API sind auf 0.0.0.0 gebunden — das ist im LAN offen."
  note "Empfohlen: 127.0.0.1 lassen und den Zugriff über den OE3-Proxy regeln."
  MANUAL+=("Bind-Adressen prüfen (REST/API auf 127.0.0.1)")
fi

# ══ 4. Stack starten ═══════════════════════════════════════════════════════
step "4/6  Stack bauen und starten (ohne Demo-Services)"
if [ "$CHECK_ONLY" = 1 ]; then
  note "--check: übersprungen"
elif [ "$SKIP_STACK" = 1 ]; then
  note "--skip-stack: übersprungen"
else
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE "mock-ris|dicom-peer"; then
    warn "Es laufen Demo-Services (mock-ris/dicom-peer) in diesem Projekt."
    note "Für den Produktivbetrieb gehören sie nicht dazu: ./build.sh (ohne --demo) startet sie nicht."
    MANUAL+=("Demo-Services entfernen: docker compose -f docker-compose.yml -f docker-compose.demo.yml down --remove-orphans")
  fi
  if [ "$DRY_RUN" = 1 ]; then
    note "[dry-run] ./build.sh --env-file $ENV_FILE --health"
  else
    # die gewählte Umgebungsdatei muss auch beim Bauen/Starten gelten
    ./build.sh --env-file "$ENV_FILE" --health \
      || fail "Der Stack wurde nicht healthy — Logs: ./build.sh --env-file $ENV_FILE --logs mwl-broker"
  fi
fi

# ══ 5. Broker konfigurieren ════════════════════════════════════════════════
API="http://127.0.0.1:$(env_get BROKER_API_PORT)/api/v1"
api_ready=0
if [ "$DRY_RUN" = 0 ] && [ "$SKIP_STACK" = 0 ]; then
  for _ in $(seq 1 20); do
    curl -sf "$API/status" >/dev/null 2>&1 && { api_ready=1; break; }
    sleep 1
  done
fi

  api_get()  { curl -sf "$API/$1" 2>/dev/null || echo ""; }
  api_put()  { # api_put KEY VALUE
    local payload
    payload="$(python3 -c 'import json,sys; print(json.dumps({"value": sys.argv[1]}))' "$2")"
    if [ "$DRY_RUN" = 1 ]; then note "[dry-run] $1 = $2"; return 0; fi
    curl -sf -X PUT "$API/settings/$1" -H 'Content-Type: application/json' \
      -H "X-OE3-Roles: brokerWrite" -H "X-OE3-User: setup" -d "$payload" >/dev/null 2>&1
  }
  api_setting() { api_get "settings/$1" | python3 -c 'import json,sys
try: print(json.load(sys.stdin)["value"])
except Exception: print("")' 2>/dev/null; }

step "5/6  Betriebseinstellungen"
if [ "$CHECK_ONLY" = 1 ]; then
  note "--check: übersprungen (nur Bericht)"
  if [ "$api_ready" = 1 ]; then
    for pair in "allowed_calling_aets:AET-Whitelist" "rbac_mode:Zugriffsschutz" "notify_webhook_url:Alarmierung"                 "tls_inbound_enabled:DICOM-TLS" "atna_enabled:ATNA" "hl7_mllp_enabled:MLLP"; do
      key="${pair%%:*}"; label="${pair#*:}"; value="$(api_setting "$key")"
      case "$key" in
        allowed_calling_aets) [ -n "$value" ] && ok "$label: $value" || warn "$label ist leer — jedes AET darf zugreifen" ;;
        rbac_mode) [ "$value" = "enforce" ] && ok "$label aktiv" || warn "$label ist aus (jeder darf ändern)" ;;
        notify_webhook_url) [ -n "$value" ] && ok "$label eingerichtet" || warn "$label fehlt — niemand erfährt von Ausfällen" ;;
        tls_inbound_enabled) [ "$value" = "true" ] && ok "$label aktiv" || note "$label ist aus (im LAN vertretbar)" ;;
        *) [ "$value" = "true" ] && ok "$label aktiv" || note "$label ist aus" ;;
      esac
    done
  fi
elif [ "$api_ready" = 0 ]; then
  note "Broker-API nicht erreichbar ($API) — Einstellungen werden übersprungen."
  note "Später nachholen: ./setup.sh --skip-stack"
  MANUAL+=("Betriebseinstellungen nachholen: ./setup.sh --skip-stack")
else
  # ── 5a. AET-Whitelist ────────────────────────────────────────────────────
  current_aets="$(api_setting allowed_calling_aets)"
  if [ -z "$current_aets" ]; then
    printf '\n%sAET-Whitelist%s\n' "$C_STEP" "$C_RESET"
    note "Ohne Whitelist darf JEDES Gerät im Netz Arbeitslisten abfragen und Bilder senden."
    note "Trage die AETs deiner Modalitäten ein (Komma-getrennt), z.B. CT_01,MR_02,DX_03"
    if confirm "Whitelist jetzt setzen?"; then
      aets="$(ask "AETs (leer = alle erlauben)" "")" || aets=""
      if [ -n "$aets" ]; then
        # jede AET prüfen, bevor sie gespeichert wird
        valid=""
        for a in ${aets//,/ }; do
          if valid_aet "$(printf '%s' "$a" | tr 'a-z' 'A-Z')"; then valid="${valid:+$valid,}$(printf '%s' "$a" | tr 'a-z' 'A-Z')"
          else warn "  '$a' sieht nicht wie ein AET aus (1–16 Zeichen, A–Z 0–9 _) — übersprungen"; fi
        done
        if [ -n "$valid" ]; then api_put allowed_calling_aets "$valid" && ok "AET-Whitelist: $valid" && CHANGED=$((CHANGED + 1))
        else warn "Keine gültige AET angegeben — Whitelist bleibt leer"; MANUAL+=("AET-Whitelist setzen"); fi
      else
        note "Leer gelassen — jedes AET darf zugreifen."
        MANUAL+=("AET-Whitelist setzen, sobald die Modalitäten bekannt sind")
      fi
    fi
  else
    ok "AET-Whitelist ist gesetzt: $current_aets"
  fi

  # ── 5b. RBAC ─────────────────────────────────────────────────────────────
  current_rbac="$(api_setting rbac_mode)"
  printf '\n%sZugriffsschutz (RBAC)%s\n' "$C_STEP" "$C_RESET"
  if [ "$current_rbac" = "enforce" ]; then
    ok "RBAC ist aktiv (enforce)"
  else
    note "Aktuell darf jeder, der die Oberfläche erreicht, die Konfiguration ändern."
    note "Mit 'enforce' braucht jede Änderung die Rolle im Header, den der Proxy setzt"
    note "($(api_setting rbac_roles_header) mit der Rolle $(api_setting rbac_write_role))."
    warn "Wichtig: Setzt der Proxy den Header NICHT, wird die Oberfläche schreibgeschützt."
    if confirm "RBAC jetzt aktivieren?"; then
      api_put rbac_mode enforce && ok "RBAC aktiv (enforce)" && CHANGED=$((CHANGED + 1))
      note "Rückgängig: curl -X PUT $API/settings/rbac_mode -H 'Content-Type: application/json' -d '{\"value\":\"off\"}'"
    else
      MANUAL+=("RBAC aktivieren, sobald der Proxy die Rolle übergibt")
    fi
  fi

  # ── 5c. DICOM-TLS ────────────────────────────────────────────────────────
  tls_state="$(api_get tls/overview)"
  printf '\n%sDICOM-TLS%s\n' "$C_STEP" "$C_RESET"
  if printf '%s' "$tls_state" | grep -q '"inbound_enabled": *true'; then
    ok "TLS-Listener ist aktiv"
  else
    note "TLS ist aus. Im LAN/VPN ist das vertretbar; sobald Modalitäten über"
    note "nicht vertrauenswürdige Netze anbinden, sollte es an sein."
    choice="$(choose "Zertifikate einrichten?" \
      "Aus lassen (später möglich)" \
      "Zertifikat + Schlüssel aus der PKI einspielen (Dateien angeben)" \
      "Selbstsigniertes Zertifikat erzeugen")"
    case "$choice" in
      2)
        cert_path="$(ask "Pfad zum Zertifikat (.crt/.pem)" "" valid_path)" || cert_path=""
        key_path="$(ask "Pfad zum privaten Schlüssel (.key/.pem)" "" valid_path)" || key_path=""
        ca_path="$(ask "Pfad zum CA-Bundle (optional)" "")" || ca_path=""
        if [ -n "$cert_path" ] && [ -f "$cert_path" ] && [ -n "$key_path" ] && [ -f "$key_path" ]; then
          payload="$(python3 - "$cert_path" "$key_path" "${ca_path:-}" <<'PY'
import json, sys
cert = open(sys.argv[1]).read()
key = open(sys.argv[2]).read()
ca = open(sys.argv[3]).read() if sys.argv[3] else ""
print(json.dumps({"certificate_pem": cert, "key_pem": key, "ca_pem": ca,
                  "filename": "uploaded", "is_ca": False}))
PY
)"
          if [ "$DRY_RUN" = 1 ]; then note "[dry-run] Zertifikat hochladen"
          elif curl -sf -X POST "$API/tls/upload" -H 'Content-Type: application/json' \
                 -H "X-OE3-Roles: brokerWrite" -d "$payload" >/dev/null; then
            ok "Zertifikat installiert"; CHANGED=$((CHANGED + 1))
          else
            warn "Der Broker hat das Zertifikat abgelehnt (Schlüssel passt nicht / abgelaufen) — siehe Meldung im UI"
            MANUAL+=("Zertifikat erneut einspielen (Meldung im TLS-Bereich beachten)")
          fi
        else
          warn "Datei nicht gefunden — übersprungen"; MANUAL+=("TLS-Zertifikate einspielen")
        fi
        ;;
      3)
        cn="$(ask "Hostname/IP des Brokers für das Zertifikat" "$(hostname -f 2>/dev/null || hostname)")" || cn=""
        san="$(ask "Weitere Adressen (Komma-getrennt, optional)" "$(hostname -I 2>/dev/null | awk '{print $1}')")" || san=""
        if [ -n "$cn" ]; then
          payload="$(python3 - "$cn" "$san" <<'PY'
import json, sys
cn = sys.argv[1]
san = [s.strip() for s in sys.argv[2].replace(",", " ").split() if s.strip()]
print(json.dumps({"common_name": cn, "days": 3650, "san": san, "is_ca": False,
                  "filename": "mwl-broker"}))
PY
)"
          if [ "$DRY_RUN" = 1 ]; then note "[dry-run] selbstsigniertes Zertifikat für $cn"
          elif curl -sf -X POST "$API/tls/self-signed" -H 'Content-Type: application/json' \
                 -H "X-OE3-Roles: brokerWrite" -d "$payload" >/dev/null; then
            ok "Selbstsigniertes Zertifikat erzeugt (für $cn)"; CHANGED=$((CHANGED + 1))
          else warn "Erzeugen fehlgeschlagen — Common Name prüfen"; MANUAL+=("TLS-Zertifikat erzeugen"); fi
        fi
        ;;
      *) note "TLS bleibt aus."; MANUAL+=("TLS aktivieren, wenn die Modalitäten es verlangen") ;;
    esac
    if [ "$choice" != "1" ] && [ "$DRY_RUN" = 0 ] && confirm "TLS-Listener jetzt einschalten?"; then
      # Pfade aus dem aktuellen Zustand übernehmen (die Karte setzt sie beim Upload)
      cert_file="$(printf '%s' "$tls_state" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("entries",{}).get("inbound_cert",{}).get("path","") or "")
except Exception: print("")' 2>/dev/null)"
      key_file="$(printf '%s' "$tls_state" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("entries",{}).get("inbound_key",{}).get("path","") or "")
except Exception: print("")' 2>/dev/null)"
      [ -n "$cert_file" ] && api_put tls_inbound_cert_file "$cert_file"
      [ -n "$key_file" ] && api_put tls_inbound_key_file "$key_file"
      api_put tls_inbound_enabled true && ok "TLS-Listener aktiviert" && CHANGED=$((CHANGED + 1))
      note "Nach dem Umschalten eine Modalität testen — Klartext läuft weiter, nichts bricht."
    fi
  fi

  # ── 5d. Alerting ─────────────────────────────────────────────────────────
  webhook="$(api_setting notify_webhook_url)"
  printf '\n%sAlarmierung%s\n' "$C_STEP" "$C_RESET"
  if [ -n "$webhook" ]; then
    ok "Webhook ist gesetzt ($(mask "$webhook"))"
    if confirm "Testnachricht senden?"; then
      result="$(curl -sf -X POST "$API/notify/test" -H "X-OE3-Roles: brokerWrite" 2>/dev/null || echo '')"
      if printf '%s' "$result" | grep -q '"ok": *true'; then ok "Testnachricht wurde angenommen"
      else warn "Der Webhook hat die Testnachricht nicht angenommen: $result"; MANUAL+=("Webhook prüfen (URL/Netzwerk)"); fi
    fi
  else
    note "Ohne Webhook erfährt niemand, wenn eine Quelle oder ein PACS ausfällt."
    if confirm "Webhook jetzt einrichten?"; then
      url="$(ask "Webhook-URL (Slack/Teams-kompatibel)" "" valid_url)" || url=""
      if [ -n "$url" ]; then
        api_put notify_webhook_url "$url" && ok "Webhook gesetzt" && CHANGED=$((CHANGED + 1))
        api_put notify_events "source_down,target_down,spool_dead_letter,spool_full,config_error,tls_certificate_expiring" \
          && note "Ereignisse gesetzt: Ausfälle, aufgegebene Bilder, volle Warteschlange, Zertifikat läuft ab"
        if confirm "Testnachricht senden?"; then
          result="$(curl -sf -X POST "$API/notify/test" -H "X-OE3-Roles: brokerWrite" 2>/dev/null || echo '')"
          printf '%s' "$result" | grep -q '"ok": *true' && ok "Testnachricht wurde angenommen" \
            || { warn "Testnachricht abgelehnt: $result"; MANUAL+=("Webhook prüfen"); }
        fi
      fi
    else
      MANUAL+=("Webhook einrichten (sonst keine Ausfallmeldungen)")
    fi
  fi

  # ── 5e. Optional: ATNA und MLLP ──────────────────────────────────────────
  printf '\n%sOptional: Audit-Trail (ATNA) und HL7 über MLLP%s\n' "$C_STEP" "$C_RESET"
  if [ "$(api_setting atna_enabled)" = "true" ]; then
    ok "ATNA ist aktiv"
  elif confirm "IHE-ATNA-Audit an eine Audit-Gegenstelle senden?"; then
    host="$(ask "Host der Audit-Gegenstelle" "" valid_host)" || host=""
    port="$(ask "Port (6514 = TLS, 514 = Klartext)" "6514" is_int)" || port=""
    if [ -n "$host" ]; then
      api_put atna_syslog_host "$host"; api_put atna_syslog_port "$port"
      api_put atna_enabled true && ok "ATNA aktiviert ($host:$port)" && CHANGED=$((CHANGED + 1))
    fi
  else
    note "ATNA bleibt aus."
  fi
  if [ "$(api_setting hl7_mllp_enabled)" = "true" ]; then
    ok "MLLP-Listener ist aktiv"
  elif confirm "Soll der Broker HL7-ORM-Nachrichten auch über MLLP annehmen?"; then
    port="$(ask "MLLP-Port" "$(api_setting hl7_mllp_port)" is_int)" || port=""
    [ -n "$port" ] && api_put hl7_mllp_port "$port"
    api_put hl7_mllp_enabled true && ok "MLLP-Listener aktiviert" && CHANGED=$((CHANGED + 1))
    MANUAL+=("Firewall für den MLLP-Port freigeben, falls das RIS von einem anderen Host sendet")
  else
    note "MLLP bleibt aus (REST-Endpunkt bleibt verfügbar)."
  fi

  # ── 5f. Aufbewahrung ─────────────────────────────────────────────────────
  printf '\n%sAufbewahrung%s\n' "$C_STEP" "$C_RESET"
  if confirm "Standard-Aufbewahrung übernehmen? (Abfragen 90 Tage, Store-Log 180, HL7 30, Spool 7, Änderungsprotokoll für immer)"; then
    api_put retention_query_log_days 90
    api_put retention_store_log_days 180
    api_put retention_hl7_days 30
    api_put retention_spool_days 7
    api_put retention_config_audit_days 0
    ok "Aufbewahrung gesetzt (0 = für immer)"; CHANGED=$((CHANGED + 1))
  else
    note "Aufbewahrung unverändert — im UI unter Broker-Einstellungen anpassbar."
    MANUAL+=("Aufbewahrung an die Haus-Policy anpassen")
  fi
fi

# ══ 6. Abschluss ═══════════════════════════════════════════════════════════
step "6/6  Prüfen und abschließen"
if [ "$api_ready" = 1 ]; then
  health="$(api_get health/config)"
  printf '%s  Konfigurations-Check:%s\n' "$C_STEP" "$C_RESET"
  printf '%s\n' "$health" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("   (nicht lesbar)"); raise SystemExit
s = d.get("summary", {})
print(f"   Fehler: {s.get(\"error\", 0)}   Warnungen: {s.get(\"warning\", 0)}   Hinweise: {s.get(\"info\", 0)}")
for f in d.get("findings", []):
    print(f"   [{f[\"severity\"]}] {f[\"message\"]}")' 2>/dev/null || true
  echo
  printf '%s  Selbsttest der DICOM-Strecke:%s\n' "$C_STEP" "$C_RESET"
  if [ "$DRY_RUN" = 0 ]; then
    python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 "$(env_get BROKER_DICOM_PORT)" "$(env_get BROKER_AET)" 2>&1 | tail -3 || \
      note "Kein C-FIND möglich (noch keine Quelle konfiguriert) — im UI unter Upstream-Quellen anlegen."
  fi
fi

echo
hr
printf '%sZusammenfassung%s\n' "$C_STEP" "$C_RESET"
hr
printf '  Geänderte Werte/Einstellungen: %d\n' "$CHANGED"
[ -n "${BACKUP_FILE:-}" ] && printf '  Sicherung der alten Konfiguration: %s\n' "$BACKUP_FILE"
printf '  Offen für dich (nicht automatisch möglich):\n'
if [ "${#MANUAL[@]}" -eq 0 ]; then printf '   • nichts — alles Wesentliche ist gesetzt\n'; fi
for item in "${MANUAL[@]}"; do printf '   • %s\n' "$item"; done
cat <<EOF

  Adressen
    Oberfläche     http://<host>:$(env_get OE3_PORT)/oe3/
    Broker-API     http://127.0.0.1:$(env_get BROKER_API_PORT)/api/v1  (Doku: /docs)
    DICOM          AET $(env_get BROKER_AET), Port $(env_get BROKER_DICOM_PORT) → Modalitäten hierher zeigen

  Nächste Schritte
    ./build.sh --logs mwl-broker     Logs ansehen
    ./setup.sh --check               jederzeit erneut prüfen (ändert nichts)
    ./ci-local.sh                    komplette Testpipeline

  Sicherung (empfohlen, z.B. als Cron)
    ./deploy/backup.sh --dir /mnt/backup --keep 30
      sichert BEIDE Datenbanken (Broker + Orthanc), das Spool-Volume und die .env
    ./deploy/backup-roundtrip-test.sh
      beweist, dass die Wiederherstellung funktioniert (sichern → löschen → zurück)
EOF
hr
