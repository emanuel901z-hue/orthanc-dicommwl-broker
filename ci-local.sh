#!/usr/bin/env bash
# ci-local.sh — local CI pipeline for the whole workspace.
#
# Runs every stage against the SAME code that the production stack ships:
# the docker e2e stage builds the images from source (./mwl-broker,
# ./orthanc-explorer-3-usable, deploy/orthanc/orthanc.json) inside the
# isolated "mwl-test" project (ports 19xxx, wiped volumes).
#
#   ./ci-local.sh            # all stages
#   ./ci-local.sh --quick    # unit stages only, no docker stack
#
# Stages: backend pytest → frontend tsc → frontend lint → vitest →
# docker e2e (C-FIND smoke + Playwright desktop/mobile via test-stack.sh).
set -uo pipefail
cd "$(dirname "$0")"

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

FAILED=()

stage() {
  local name="$1"; shift
  echo ""
  echo "━━━ $name ━━━"
  if "$@"; then
    echo "── $name: PASS"
  else
    echo "── $name: FAIL ($?)"
    FAILED+=("$name")
  fi
}

# the operator scripts are code too: syntax, help text and the dry-run must work
stage "scripts" bash -c '
  set -e
  for script in setup.sh build.sh bootstrap.sh ci-local.sh test-stack.sh pre-push-fork.sh mfa-test.sh deploy/backup.sh deploy/backup-roundtrip-test.sh deploy/ha-smoke.sh deploy/interop-test.sh; do
    [ -f "$script" ] || { echo "missing: $script"; exit 1; }
    bash -n "$script" || { echo "syntax error: $script"; exit 1; }
  done
  ./build.sh --help | grep -q "SERVICE" || { echo "build.sh --help incomplete"; exit 1; }
  ./build.sh --check | tail -1 | grep -q "Vorprüfung" || { echo "build.sh --check broken"; exit 1; }
  ./build.sh --dry-run --demo | grep -q "docker-compose.demo.yml" || { echo "build.sh --dry-run broken"; exit 1; }
  ./build.sh --dry-run | grep -q "Dry-Run" || { echo "build.sh dry-run guard missing"; exit 1; }
  ./bootstrap.sh --check >/dev/null || { echo "bootstrap.sh wrapper broken"; exit 1; }
  ./setup.sh --self-test | grep -q "alle Prüfungen ok" || { echo "setup.sh --self-test broken"; exit 1; }
  ./setup.sh --help | grep -q "check" || { echo "setup.sh --help incomplete"; exit 1; }
  ./setup.sh --env-file .env.test --check | grep -q "Produktiv-Inbetriebnahme" || { echo "setup.sh --check broken"; exit 1; }
  node orthanc-explorer-3-usable/e2e/stack/verify-screens.cjs --help >/dev/null 2>&1 || true
  echo "   scripts ok"
'

stage "backend: pytest"   bash -c 'cd mwl-broker && .venv/bin/pytest tests -q'
stage "frontend: tsc"     bash -c 'cd orthanc-explorer-3-usable && npx tsc --noEmit -p tsconfig.app.json'
stage "frontend: lint"    bash -c 'cd orthanc-explorer-3-usable && npm run lint'
stage "frontend: i18n"    bash -c 'cd orthanc-explorer-3-usable && npm run i18n:check'
stage "frontend: vitest"  bash -c 'cd orthanc-explorer-3-usable && npm run test'

if [ "$QUICK" -eq 0 ]; then
  stage "stack: e2e (cfind + playwright)" ./test-stack.sh
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "CI LOCAL: all stages passed"
  exit 0
else
  echo "CI LOCAL: failed stages: ${FAILED[*]}"
  exit 1
fi
