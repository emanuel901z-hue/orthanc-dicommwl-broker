#!/usr/bin/env bash
# bootstrap.sh — Kompatibilitäts-Wrapper um ./build.sh.
#
# Die frühere "plug-and-play"-Variante für einen frischen Ubuntu-Server lebt
# jetzt in build.sh (bauen, starten, prüfen, stoppen, Registry). Dieses Script
# bleibt erhalten, damit ältere Anleitungen und Kommandos weiter funktionieren:
#
#   ./bootstrap.sh            → ./build.sh
#   ./bootstrap.sh --demo     → ./build.sh --demo
#   ./bootstrap.sh --viewer   → ./build.sh --viewer
#   ./bootstrap.sh --check    → ./build.sh --check
#
# Alle Optionen und Erklärungen: ./build.sh --help
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ./build.sh ]; then
  echo "FAIL: build.sh fehlt oder ist nicht ausführbar (chmod +x build.sh)" >&2
  exit 1
fi

# Wie bisher: auf einem frischen Server Docker gleich mitinstallieren, statt
# nur mit einer Anleitung abzubrechen. build.sh macht das nur auf Wunsch.
EXTRA=()
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Docker fehlt — wird wie bisher installiert (build.sh --install-docker)"
  EXTRA+=(--install-docker)
fi

echo "==> bootstrap.sh leitet an build.sh weiter (Details: ./build.sh --help)"
exec ./build.sh ${EXTRA[@]+"${EXTRA[@]}"} "$@"
