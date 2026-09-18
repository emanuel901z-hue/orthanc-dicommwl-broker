#!/usr/bin/env bash
# MFA-Testumgebung: unbedarfter Anwender, kompletter Durchlauf mit Fehlern.
#
#   ./mfa-test.sh              # Stack hochfahren + MFA-Journey fahren
#   ./mfa-test.sh --keep       # Stack danach laufen lassen
#
# Ergebnis: orthanc-explorer-3-usable/e2e/stack/screenshots/mfa-journey-*.md
set -euo pipefail
cd "$(dirname "$0")"

KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

echo "── Test-Stack starten (isoliert, eigene Ports) ──"
docker compose --project-name mwl-test --env-file .env.test \
  -f docker-compose.yml -f docker-compose.demo.yml up -d --build >/dev/null
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:19081/healthz >/dev/null 2>&1 && break
  sleep 2
done
sleep 3

echo "── MFA-Journey (Chromium, Desktop + Mobile) ──"
cd orthanc-explorer-3-usable
OE3_BASE=http://127.0.0.1:19082 npx playwright test \
  --config=e2e/stack/playwright.stack.config.ts mfa-journey.spec.ts || true

echo
echo "── Bericht ──"
for report in e2e/stack/screenshots/mfa-journey-*.md; do
  [[ -f "$report" ]] && { echo "### $report"; cat "$report"; echo; }
done

if [[ $KEEP -eq 0 ]]; then
  echo "── Stack stoppen ──"
  cd .. && docker compose --project-name mwl-test --env-file .env.test \
    -f docker-compose.yml -f docker-compose.demo.yml down -v >/dev/null 2>&1 || true
fi
