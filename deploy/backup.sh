#!/usr/bin/env bash
# backup.sh — Sicherung des MWL-Broker-Stacks (Datenbank, Spool, Konfiguration).
#
# Gesichert wird alles, was einen Neuaufbau überlebt haben muss:
#   1. Postgres (Worklist-Cache, Protokolle, MPPS-Schritte, lokale Einträge,
#      Änderungsprotokoll, Konfiguration)  → pg_dump
#   2. Spool-Verzeichnis (gepufferte Bilder, die noch nicht zugestellt sind)
#   3. .env (Ports, Zugangsdaten) — ohne die ist eine Wiederherstellung Rätselraten
#
# Aufrufe:
#   ./deploy/backup.sh                 Sicherung nach ./backups/<Zeitstempel>/
#   ./deploy/backup.sh --dir /mnt/nas  anderes Zielverzeichnis
#   ./deploy/backup.sh --keep 30       nur die letzten 30 Sicherungen behalten
#   ./deploy/backup.sh --list          vorhandene Sicherungen zeigen
#   ./deploy/backup.sh --restore PATH  Wiederherstellung (fragt nach!)
#   ./deploy/backup.sh --restore PATH --yes   ohne Rückfrage (für Skripte)
#   ./deploy/backup.sh --check         nur prüfen (Docker, Platz, letzte Sicherung)
#
# Das Script löscht nichts außer alten Sicherungen (--keep) und verweigert die
# Wiederherstellung ohne ausdrückliche Bestätigung.
set -euo pipefail
cd "$(dirname "$0")/.."

DIR="${BACKUP_DIR:-./backups}"
KEEP=14
MODE="backup"
RESTORE_FROM=""
ENV_FILE=".env"
ASSUME_YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="${2:-}"; [ -n "$DIR" ] || { echo "--dir braucht einen Pfad" >&2; exit 2; }; shift ;;
    --keep) KEEP="${2:-}"; [ -n "$KEEP" ] || { echo "--keep braucht eine Zahl" >&2; exit 2; }; shift ;;
    --env-file) ENV_FILE="${2:-}"; shift ;;
    --list) MODE="list" ;;
    --check) MODE="check" ;;
    --restore) MODE="restore"; RESTORE_FROM="${2:-}"; [ -n "$RESTORE_FROM" ] || { echo "--restore braucht einen Pfad" >&2; exit 2; }; shift ;;
    --yes) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unbekannte Option: $1 (--help zeigt alles)" >&2; exit 2 ;;
  esac
  shift
done

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN:\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

# .env als Daten lesen (Werte mit Leerzeichen sind erlaubt)
load_env() {
  [ -f "$ENV_FILE" ] || return 0
  local line key value
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; *=*) ;; *) continue ;; esac
    key="${line%%=*}"; value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    case "$value" in \"*\") value="${value#\"}"; value="${value%\"}" ;; \'*\') value="${value#\'}"; value="${value%\'}" ;; esac
    [ -n "$key" ] && export "$key=$value"
  done < "$ENV_FILE"
}
load_env

PROJECT="${COMPOSE_PROJECT_NAME:-mwl-broker}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml)

# Which databases live in this Postgres? The broker keeps its own (`mwl`), the
# bundled Orthanc has `orthanc`. Dumping the wrong one is the classic silent
# backup mistake — so the names are read from the compose file, not guessed.
detect_databases() {
  local found
  found="$(grep -oE 'BROKER_DATABASE_URL: [^ ]*' docker-compose.yml 2>/dev/null \
    | grep -oE '/[a-zA-Z0-9_]+$' | tr -d '/' | sort -u)"
  [ -n "$found" ] || found="mwl"
  printf '%s\n' $found
  grep -q 'POSTGRES_DB: orthanc' docker-compose.yml 2>/dev/null && echo orthanc
}
mapfile -t DATABASES < <(detect_databases | sort -u)
[ "${#DATABASES[@]}" -gt 0 ] || DATABASES=(mwl)

# ── Liste ──────────────────────────────────────────────────────────────────
if [ "$MODE" = "list" ]; then
  [ -d "$DIR" ] || { echo "Keine Sicherungen in $DIR"; exit 0; }
  info "Sicherungen in $DIR:"
  for entry in "$DIR"/*/; do
    [ -d "$entry" ] || continue
    size="$(du -sh "$entry" 2>/dev/null | cut -f1)"
    printf '  %-28s %s\n' "$(basename "$entry")" "$size"
  done
  exit 0
fi

# ── Vorprüfung ─────────────────────────────────────────────────────────────
check_only=0
[ "$MODE" = "check" ] && check_only=1
info "Voraussetzungen prüfen"
command -v docker >/dev/null 2>&1 || fail "Docker fehlt"
docker info >/dev/null 2>&1 || fail "Kein Zugriff auf den Docker-Daemon"
ok "Docker erreichbar"

if ! "${COMPOSE[@]}" ps --services --filter status=running 2>/dev/null | grep -q postgres; then
  fail "Der Postgres-Container läuft nicht — Sicherung nicht möglich.
      Starten: ./build.sh, dann erneut versuchen."
fi
ok "Postgres läuft (Projekt $PROJECT)"

if [ "$check_only" = 1 ]; then
  if [ -d "$DIR" ]; then
    newest="$(ls -1dt "$DIR"/*/ 2>/dev/null | head -1 || true)"
    if [ -n "$newest" ]; then
      age_days=$(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 86400 ))
      if [ "$age_days" -gt 2 ]; then warn "Die letzte Sicherung ist $age_days Tage alt: $newest"
      else ok "Letzte Sicherung: $(basename "$newest") ($age_days Tage alt)"; fi
    else warn "Keine Sicherung gefunden in $DIR"; fi
  else
    warn "Zielverzeichnis $DIR existiert noch nicht"
  fi
  free_mb="$(df -Pm "$(dirname "$DIR")" 2>/dev/null | awk 'NR==2 {print $4}')"
  [ -n "${free_mb:-}" ] && { [ "$free_mb" -lt 1024 ] && warn "Nur ${free_mb} MB frei auf $(dirname "$DIR")" || ok "${free_mb} MB frei auf $(dirname "$DIR")"; }
  exit 0
fi

# ── Wiederherstellung ──────────────────────────────────────────────────────
if [ "$MODE" = "restore" ]; then
  [ -d "$RESTORE_FROM" ] || fail "Sicherung nicht gefunden: $RESTORE_FROM"
  mapfile -t db_files < <(ls -1 "$RESTORE_FROM"/postgres-*.sql.gz 2>/dev/null || true)
  [ "${#db_files[@]}" -gt 0 ] || fail "In $RESTORE_FROM liegt kein postgres-*.sql.gz"
  warn "Die Wiederherstellung ERSETZT die aktuelle Datenbank (Cache, Protokolle,"
  warn "lokale Einträge, Änderungsprotokoll) und die gepufferten Bilder."
  if [ "$ASSUME_YES" = 0 ]; then
    # /dev/tty fehlt in Skripten und Containern — dann von stdin lesen
    tty_in="/dev/tty"; [ -r /dev/tty ] || tty_in="/dev/stdin"
    printf 'Zum Fortfahren "WIEDERHERSTELLEN" eingeben (oder --yes): '
    read -r answer <"$tty_in" || answer=""
    [ "$answer" = "WIEDERHERSTELLEN" ] || fail "abgebrochen (nichts geändert)"
  fi

  # Die Anwendungen halten Verbindungen auf die Datenbank — ein DROP schlägt
  # sonst mit "is being accessed by other users" fehl. Also erst stoppen.
  info "Dienste stoppen (Broker, Orthanc), damit die Datenbank frei ist"
  "${COMPOSE[@]}" stop mwl-broker orthanc >/dev/null 2>&1 || true

  for db_file in "${db_files[@]}"; do
    # Dateiname: postgres-<db>-<stamp>.sql.gz  (bzw. ältere Sicherungen ohne db)
    db="$(basename "$db_file" | sed -E 's/^postgres-//; s/-[0-9]{8}-[0-9]{6}\.sql\.gz$//')"
    [ "$db" = "postgres" ] && db="orthanc"
    info "Datenbank '$db' wiederherstellen"
    "${COMPOSE[@]}" exec -T postgres psql -U "${POSTGRES_USER:-dev}" -d postgres \
      -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid();" \
      >/dev/null 2>&1 || true
    "${COMPOSE[@]}" exec -T postgres psql -U "${POSTGRES_USER:-dev}" -d postgres \
      -c "DROP DATABASE IF EXISTS \"$db\";" -c "CREATE DATABASE \"$db\";" >/dev/null
    # ON_ERROR_STOP: ein halb eingespielter Dump wäre schlimmer als ein Fehler
    if ! gunzip -c "$db_file" | "${COMPOSE[@]}" exec -T postgres \
        psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-dev}" -d "$db" \
        > "$RESTORE_FROM/restore-$db.log" 2>&1; then
      tail -20 "$RESTORE_FROM/restore-$db.log" >&2
      fail "Wiederherstellung von $db fehlgeschlagen (Details: $RESTORE_FROM/restore-$db.log)"
    fi
    rows="$("${COMPOSE[@]}" exec -T postgres psql -tAU "${POSTGRES_USER:-dev}" -d "$db" \
      -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d '[:space:]')"
    [ "${rows:-0}" -ge 1 ] || fail "Nach der Wiederherstellung fehlen Tabellen in $db ($rows)"
    ok "Datenbank '$db' wiederhergestellt ($rows Tabellen)"
  done



  if [ -f "$RESTORE_FROM/env" ]; then
    warn "Die gesicherte .env liegt unter $RESTORE_FROM/env — bitte bei Bedarf"
    warn "manuell übernehmen (Zugangsdaten/Ports) und danach ./build.sh ausführen."
  fi
  info "Dienste wieder starten"
  "${COMPOSE[@]}" start mwl-broker orthanc >/dev/null 2>&1 || true

  if [ -f "$RESTORE_FROM/spool.tar.gz" ]; then
    # erst nach dem Start: `compose exec` braucht einen laufenden Container
    info "Spool-Verzeichnis wiederherstellen"
    "${COMPOSE[@]}" exec -T mwl-broker mkdir -p /var/lib/mwl-broker/spool
    "${COMPOSE[@]}" exec -T mwl-broker tar xzf - -C /var/lib/mwl-broker/spool \
      < "$RESTORE_FROM/spool.tar.gz"
    ok "Spool wiederhergestellt"
  fi
  ok "fertig — bitte ./setup.sh --check laufen lassen"
  exit 0
fi

# ── Sicherung ──────────────────────────────────────────────────────────────
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$DIR/$STAMP"
mkdir -p "$TARGET"

info "Sicherung nach $TARGET"
free_mb="$(df -Pm "$(dirname "$DIR")" | awk 'NR==2 {print $4}')"
[ "${free_mb:-99999}" -lt 512 ] && fail "Zu wenig Platz (${free_mb} MB) auf $(dirname "$DIR")"

for db in "${DATABASES[@]}"; do
  db_file="$TARGET/postgres-$db-$STAMP.sql.gz"
  "${COMPOSE[@]}" exec -T postgres pg_dump -U "${POSTGRES_USER:-dev}" -d "$db" \
    | gzip > "$db_file"
  # Eine leere oder abgebrochene Sicherung ist wertlos — sofort prüfen
  [ -s "$db_file" ] || fail "Die Sicherung von $db ist leer — pg_dump ist fehlgeschlagen"
  tables="$(zcat "$db_file" | grep -c "^CREATE TABLE" || true)"
  [ "${tables:-0}" -ge 1 ] || fail "Die Sicherung von $db enthält keine Tabellen — unvollständig"
  ok "Datenbank '$db' gesichert: $(du -h "$db_file" | cut -f1), $tables Tabellen"
done

spool_size="$("${COMPOSE[@]}" exec -T mwl-broker du -sh /var/lib/mwl-broker/spool 2>/dev/null | cut -f1 || echo "?")"
if "${COMPOSE[@]}" exec -T mwl-broker test -d /var/lib/mwl-broker/spool 2>/dev/null; then
  "${COMPOSE[@]}" exec -T mwl-broker tar czf - -C /var/lib/mwl-broker/spool . \
    > "$TARGET/spool.tar.gz"
  ok "Spool gesichert ($spool_size)"
fi

if [ -f "$ENV_FILE" ]; then
  cp "$ENV_FILE" "$TARGET/env"
  chmod 600 "$TARGET/env"
  ok "Konfiguration gesichert ($ENV_FILE)"
fi

# Kurzbericht für die spätere Kontrolle
{
  echo "Zeitpunkt: $(date -Iseconds)"
  echo "Projekt:   $PROJECT"
  echo "Datenbank: $(du -h "$db_file" | cut -f1)"
  echo "Spool:     $spool_size"
  echo "Broker:    $("${COMPOSE[@]}" exec -T mwl-broker python -c 'from mwl_broker import __version__; print(__version__)' 2>/dev/null | tr -d '\r' || echo '?')"
} > "$TARGET/INFO.txt"
ok "Bericht geschrieben (INFO.txt)"

# Aufräumen: nur die letzten $KEEP behalten
if [ "$KEEP" -gt 0 ]; then
  mapfile -t old < <(ls -1dt "$DIR"/*/ 2>/dev/null | tail -n +"$((KEEP + 1))")
  if [ "${#old[@]}" -gt 0 ]; then
    info "Alte Sicherungen entfernen (behalte $KEEP)"
    for entry in "${old[@]}"; do
      rm -rf "$entry"
      printf '  entfernt: %s\n' "$(basename "$entry")"
    done
  fi
fi

printf '\n%sSicherung abgeschlossen:%s %s\n' '\033[1;32m' '\033[0m' "$TARGET"
echo "Wiederherstellen (ersetzt die Datenbank, fragt nach):"
echo "  ./deploy/backup.sh --restore $TARGET"
