#!/usr/bin/env bash
# build.sh — build, start and operate the MWL broker stack.
#
#   ./build.sh                     base stack (postgres, orthanc, broker, oe3)
#   ./build.sh --demo              additionally the mock RIS sources + peer PACS
#   ./build.sh --viewer            additionally the OHIF viewer (slow build)
#   ./build.sh mwl-broker oe3      only these services
#   ./build.sh --check             preflight only (docker, .env, ports)
#   ./build.sh --logs mwl-broker   follow the logs of one service
#   ./build.sh --down              stop the stack (--volumes to drop data)
#
# Idempotent: re-running rebuilds what changed and leaves the rest alone.
# Every option is explained in --help; the script never touches other projects
# on the host (only the ports from .env are used, all bind to 127.0.0.1).
set -euo pipefail
cd "$(dirname "$0")"

# ── defaults ─────────────────────────────────────────────────────────────────
DEMO=0
VIEWER=0
ALL=0
CHECK_ONLY=0
NO_CACHE=0
PULL=0
PUSH=0
TAG=""
HEALTH_WAIT=0
SHOW_PS=0
FOLLOW_LOGS=""
DO_DOWN=0
DROP_VOLUMES=0
RESTART=0
DRY_RUN=0
ASSUME_YES=0
VERBOSE=0
INSTALL_DOCKER=0
ENV_FILE=".env"
SERVICES=()

usage() {
  cat <<'EOF'
build.sh — baut, startet und bedient den MWL-Broker-Stack

AUFRUF
  ./build.sh [OPTIONEN] [SERVICE ...]

  Ohne Optionen wird der Basis-Stack gebaut und gestartet
  (postgres, orthanc, mwl-broker, oe3). Werden Services genannt, passiert nur
  mit diesen etwas — z. B. `./build.sh mwl-broker` nach einer Code-Änderung.

UMFANG
  --demo                 zusätzlich die Demo-Services (mock-ris-a/-b, dicom-peer).
                         Nur für Tests/Demos — nie auf einem Produktivhost nötig.
  --viewer               zusätzlich den OHIF-Viewer (Compose-Profil "viewer").
                         Der Build klont und kompiliert OHIF: 5–10 Minuten.
  --all                  Basis + Demo + Viewer.

BAUEN
  --no-cache             Images ohne Docker-Cache bauen (nach Dependency-Wechsel).
  --pull                 Basis-Images (python, postgres, nginx, orthanc) vorher
                         aktualisieren.
  --tag PREFIX           Gebaute Images zusätzlich als PREFIX/<name>:<version>
                         taggen — für eine Registry (siehe --push).
  --push                 Getaggte Images in die Registry pushen (braucht --tag).
  --install-docker       Docker installieren, falls es fehlt (get.docker.com).
                         Ohne diese Option bricht das Script mit einer Anleitung ab.

BETRIEB
  --check                Nur Vorprüfung: Docker, .env, Ports. Baut nichts.
  --health               Nach dem Start warten, bis alle Services "healthy" sind
                         (mit Timeout; zeigt sonst die Logs des Problemfalls).
  --ps                   Nur die Statustabelle zeigen.
  --logs [SERVICE]       Logs folgen (ohne Service: alle). Beenden mit Strg-C.
  --restart              Container neu starten, ohne neu zu bauen.
  --down                 Stack stoppen (Container + Netz bleiben die Volumes).
  --volumes              Zusammen mit --down: Volumes löschen. ACHTUNG: löscht
                         Postgres-Daten, Spool-Payloads und Orthanc-Instanzen.

SONSTIGES
  --env-file DATEI       Andere Umgebungsdatei verwenden (Default: .env).
  --dry-run              Nur anzeigen, was ausgeführt würde.
  --yes                  Nicht nachfragen (für Skripte/CI).
  -v, --verbose          Vollständige Docker-Ausgabe.
  -h, --help             Diese Hilfe.

BEISPIELE
  ./build.sh --check                          Vorprüfung, bevor irgendwas läuft
  ./build.sh --demo --health                  Demo-Stack bauen und auf Health warten
  ./build.sh --no-cache mwl-broker oe3        nach Dependency-Änderungen
  ./build.sh --tag registry.haus.local/mwl --push   Images für eine Registry bauen
  ./build.sh --logs mwl-broker                Logs des Brokers ansehen
  ./build.sh --down --volumes --yes           Alles inklusive Daten entfernen
EOF
}

# ── argument parsing ─────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --demo) DEMO=1 ;;
    --viewer) VIEWER=1 ;;
    --all) DEMO=1; VIEWER=1; ALL=1 ;;
    --no-cache) NO_CACHE=1 ;;
    --pull) PULL=1 ;;
    --tag) TAG="${2:-}"; [ -n "$TAG" ] || { echo "--tag braucht ein Präfix" >&2; exit 2; }; shift ;;
    --push) PUSH=1 ;;
    --install-docker) INSTALL_DOCKER=1 ;;
    --check) CHECK_ONLY=1 ;;
    --health) HEALTH_WAIT=1 ;;
    --ps) SHOW_PS=1 ;;
    --logs) FOLLOW_LOGS="${2:-ALL}"; [ "$FOLLOW_LOGS" = "ALL" ] || shift ;;
    --restart) RESTART=1 ;;
    --down) DO_DOWN=1 ;;
    --volumes) DROP_VOLUMES=1 ;;
    --env-file) ENV_FILE="${2:-}"; [ -n "$ENV_FILE" ] || { echo "--env-file braucht einen Pfad" >&2; exit 2; }; shift ;;
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    -v|--verbose) VERBOSE=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unbekannte Option: $1 (--help zeigt alle)" >&2; exit 2 ;;
    *) SERVICES+=("$1") ;;
  esac
  shift
done

# ── output helpers ───────────────────────────────────────────────────────────
info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN:\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '   \033[2m$ %s\033[0m\n' "$*"
    return 0
  fi
  if [ "$VERBOSE" = 1 ]; then "$@"; else "$@" >/dev/null; fi
}

ask() {
  [ "$ASSUME_YES" = 1 ] && return 0
  printf '\033[1;33m%s [j/N] \033[0m' "$1"
  read -r answer </dev/tty || return 1
  case "$answer" in j|J|y|Y) return 0 ;; *) return 1 ;; esac
}

# ── 1. docker ────────────────────────────────────────────────────────────────
info "Docker prüfen…"
if ! command -v docker >/dev/null 2>&1; then
  if [ "$INSTALL_DOCKER" = 1 ]; then
    info "Docker fehlt — Installation über get.docker.com"
    run sh -c 'curl -fsSL https://get.docker.com | sh'
  else
    fail "Docker ist nicht installiert. Entweder ./build.sh --install-docker oder:
      curl -fsSL https://get.docker.com | sh
      sudo usermod -aG docker \$USER   # danach neu einloggen"
  fi
fi
docker compose version >/dev/null 2>&1 || fail "docker compose (Plugin) fehlt — Paket docker-compose-plugin installieren"
if ! docker info >/dev/null 2>&1; then
  if id -nG | grep -qw docker; then
    fail "Docker-Daemon nicht erreichbar — ab- und wieder anmelden oder: newgrp docker"
  fi
  fail "Kein Zugriff auf den Docker-Daemon. Einmalig: sudo usermod -aG docker \$USER && newgrp docker"
fi
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo ok) mit Compose"

# ── 2. environment file ──────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  if [ "$ENV_FILE" = ".env" ] && [ -f .env.example ]; then
    info ".env fehlt — aus .env.example anlegen (Ports/Passwörter vor dem Start prüfen!)"
    run cp .env.example .env
  else
    fail "Umgebungsdatei $ENV_FILE fehlt"
  fi
fi
# A dotenv file is data, not shell code: read KEY=VALUE line by line. Sourcing it
# would execute values with spaces as commands ("ORTHANC_NAME=MWL Broker Orthanc")
# and would let a manipulated file run arbitrary code.
load_env() {
  local line key value
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
      *=*) ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    value="${line#*=}"
    # trim surrounding whitespace and optional quotes
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    case "$value" in
      \"*\") value="${value#\"}"; value="${value%\"}" ;;
      \'*\') value="${value#\'}"; value="${value%\'}" ;;
    esac
    [ -n "$key" ] && export "$key=$value"
  done < "$ENV_FILE"
}
load_env
ok "Umgebung aus $ENV_FILE geladen"

# ── 3. compose files + profiles ──────────────────────────────────────────────
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml)
[ "$DEMO" = 1 ] && COMPOSE+=(-f docker-compose.demo.yml)
PROFILE_ARGS=()
# the OHIF image compiles OHIF from source — keep it behind a profile
[ "$VIEWER" = 1 ] && PROFILE_ARGS+=(--profile viewer)

if [ "$DO_DOWN" = 1 ]; then
  DOWN_ARGS=(down --remove-orphans)
  if [ "$DROP_VOLUMES" = 1 ]; then
    warn "--volumes löscht Postgres-Daten, Spool-Payloads und Orthanc-Instanzen."
    ask "Wirklich alle Daten löschen?" || fail "abgebrochen"
    DOWN_ARGS+=(-v)
  fi
  info "Stack stoppen…"
  run "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" "${DOWN_ARGS[@]}"
  ok "gestoppt"
  exit 0
fi

if [ "$SHOW_PS" = 1 ] && [ "$CHECK_ONLY" = 0 ] && [ ${#SERVICES[@]} -eq 0 ] && [ "$RESTART" = 0 ]; then
  "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" ps
  exit 0
fi

if [ -n "$FOLLOW_LOGS" ]; then
  info "Logs folgen (Strg-C beendet)…"
  if [ "$FOLLOW_LOGS" = "ALL" ]; then
    exec "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" logs -f --tail 100
  fi
  exec "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" logs -f --tail 200 "$FOLLOW_LOGS"
fi

if [ "$RESTART" = 1 ]; then
  info "Container neu starten (ohne Neu-Build)…"
  run "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" restart ${SERVICES[@]+"${SERVICES[@]}"}
  ok "neu gestartet"
  exit 0
fi

# ── 4. port check (the host runs other docker projects) ──────────────────────
info "Host-Ports prüfen…"
# postgres stays internal on purpose — no host port to check
declare -A PORT_SERVICE=(
  ["${ORTHANC_HTTP_PORT:-8042}"]="orthanc (REST)"
  ["${ORTHANC_DICOM_PORT:-4242}"]="orthanc (DICOM)"
  ["${BROKER_API_PORT:-8081}"]="mwl-broker (API)"
  ["${BROKER_DICOM_PORT:-11113}"]="mwl-broker (DICOM)"
  ["${BROKER_TLS_PORT:-2762}"]="mwl-broker (DICOM TLS)"
  ["${OE3_PORT:-8082}"]="oe3 (UI)"
)
if [ "$DEMO" = 1 ]; then
  PORT_SERVICE["${MOCK_RIS_A_PORT:-11114}"]="mock-ris-a"
  PORT_SERVICE["${MOCK_RIS_B_PORT:-11115}"]="mock-ris-b"
  PORT_SERVICE["${PEER_HTTP_PORT:-8043}"]="dicom-peer (REST)"
  PORT_SERVICE["${PEER_DICOM_PORT:-4243}"]="dicom-peer (DICOM)"
fi
if [ "$VIEWER" = 1 ]; then
  PORT_SERVICE["${OHIF_PORT:-8083}"]="ohif (Viewer)"
fi

collisions=0
for port in "${!PORT_SERVICE[@]}"; do
  [ -z "$port" ] && continue
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}$"; then
    # our own containers already hold their ports — that is not a collision
    if docker ps --format '{{.Ports}}' | grep -q ":${port}->"; then
      ok "Port $port gehört bereits zu diesem Stack (${PORT_SERVICE[$port]})"
    else
      warn "Port $port (${PORT_SERVICE[$port]}) ist von einem anderen Prozess belegt — in $ENV_FILE anpassen"
      collisions=$((collisions + 1))
    fi
  else
    ok "Port $port frei (${PORT_SERVICE[$port]})"
  fi
done
[ "$collisions" -gt 0 ] && warn "$collisions Port-Konflikt(e) — docker compose wird beim belegten Port abbrechen"

if [ "$CHECK_ONLY" = 1 ]; then
  info "Vorprüfung abgeschlossen — nichts gebaut oder gestartet."
  exit 0
fi

# ── 5. build + start ─────────────────────────────────────────────────────────
BUILD_ARGS=(build)
[ "$NO_CACHE" = 1 ] && BUILD_ARGS+=(--no-cache)
[ "$PULL" = 1 ] && BUILD_ARGS+=(--pull)
[ "$VERBOSE" = 1 ] && BUILD_ARGS+=(--progress plain)

info "Images bauen…"
run "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" "${BUILD_ARGS[@]}" ${SERVICES[@]+"${SERVICES[@]}"}

info "Stack starten…"
run "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" up -d --remove-orphans ${SERVICES[@]+"${SERVICES[@]}"}

# ── 6. optional: tag + push for a registry ───────────────────────────────────
if [ -n "$TAG" ]; then
  VERSION="$(grep -m1 '^version' mwl-broker/pyproject.toml 2>/dev/null | cut -d'"' -f2 || echo latest)"
  info "Images für die Registry taggen ($TAG, Version $VERSION)…"
  for image in $(docker compose --env-file "$ENV_FILE" -f docker-compose.yml config --images 2>/dev/null | sort -u); do
    case "$image" in
      *mwl-broker*|*oe3*|*mock-ris*|*ohif*)
        run docker tag "$image" "$TAG/$(basename "$image"):$VERSION"
        ok "$image → $TAG/$(basename "$image"):$VERSION"
        ;;
    esac
  done
  if [ "$PUSH" = 1 ]; then
    info "Images pushen…"
    for image in $(docker images --format '{{.Repository}}:{{.Tag}}' | grep "^$TAG/" || true); do
      run docker push "$image"
      ok "gepusht: $image"
    done
  else
    info "--push nicht gesetzt: Images sind getaggt, aber nicht hochgeladen."
  fi
fi

# ── 7. wait for health ───────────────────────────────────────────────────────
wait_http() {
  local name="$1" url="$2" service="$3" deadline=$((SECONDS + 180))
  until curl -sf --max-time 3 "$url" >/dev/null 2>&1; do
    if [ $SECONDS -gt $deadline ]; then
      warn "$name wurde nicht erreichbar — Logs:"
      "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" logs --tail 20 "$service" || true
      return 1
    fi
    sleep 2
  done
  ok "$name erreichbar"
}

if [ "$DRY_RUN" = 1 ]; then
  info "Dry-Run: nichts gebaut, nichts gestartet, keine Health-Prüfung."
  exit 0
fi

info "Auf Erreichbarkeit warten…"
wait_http "orthanc" "http://127.0.0.1:${ORTHANC_HTTP_PORT:-8042}/system" orthanc
wait_http "mwl-broker" "http://127.0.0.1:${BROKER_API_PORT:-8081}/healthz" mwl-broker
wait_http "oe3" "http://127.0.0.1:${OE3_PORT:-8082}/oe3/" oe3

if [ "$HEALTH_WAIT" = 1 ]; then
  info "Warten, bis alle Container \"healthy\" melden…"
  deadline=$((SECONDS + 240))
  while :; do
    unhealthy="$("${COMPOSE[@]}" "${PROFILE_ARGS[@]}" ps --format '{{.Service}} {{.Status}}' \
      | grep -E 'starting|unhealthy' || true)"
    if [ -z "$unhealthy" ]; then ok "alle Container healthy"; break; fi
    if [ $SECONDS -gt $deadline ]; then
      warn "Noch nicht healthy:"
      printf '%s\n' "$unhealthy" | sed 's/^/     /' >&2
      break
    fi
    sleep 3
  done
fi

# ── 8. summary ───────────────────────────────────────────────────────────────
"${COMPOSE[@]}" "${PROFILE_ARGS[@]}" ps --format 'table {{.Service}}\t{{.Status}}' || true

cat <<EOF

────────────────────────────────────────────────────────────────────────────
 Stack läuft.

   OE3-Oberfläche   http://<host>:${OE3_PORT:-8082}/oe3/
   Broker-API       http://127.0.0.1:${BROKER_API_PORT:-8081}/api/v1
   Broker-Doku      http://127.0.0.1:${BROKER_API_PORT:-8081}/docs
   Broker-Metriken  http://127.0.0.1:${BROKER_API_PORT:-8081}/metrics
   Orthanc-REST     http://127.0.0.1:${ORTHANC_HTTP_PORT:-8042}

   DICOM (Modalität → Broker): AET ${BROKER_AET:-MWLBROKER}, Port ${BROKER_DICOM_PORT:-11113}
   DICOM (direkt → Orthanc):   AET ${ORTHANC_AET:-ORTHANC}, Port ${ORTHANC_DICOM_PORT:-4242}

 MWL-Pfad testen:
   python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 ${BROKER_DICOM_PORT:-11113} ${BROKER_AET:-MWLBROKER}

 Weiter:
   ./build.sh --logs mwl-broker     Logs ansehen
   ./build.sh --health              Health-Status prüfen
   ./build.sh --down                Stack stoppen
   ./ci-local.sh                    komplette Testpipeline
────────────────────────────────────────────────────────────────────────────
EOF
