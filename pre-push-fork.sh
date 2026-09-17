#!/usr/bin/env bash
# pre-push-fork.sh — safety gate before pushing ANY of the two public repos.
#
#   ./pre-push-fork.sh                      # OE3 fork (default)
#   ./pre-push-fork.sh --repo .             # broker workspace repo
#   ./pre-push-fork.sh --repo . --dry-run   # audit only
#
# Audits exactly what THIS push would publish (commits + files vs origin/main):
#   1. clean worktree, correct remote (never upstream rhavekost/orthanc-explorer-3)
#   2. file blacklist: .env*, databases, keys, screenshots, test-results, histories, …
#   3. secret-pattern scan over the outgoing diff
#   4. optional quick checks (--tests: tsc + vitest, fork only)
# Then pushes only after explicit confirmation.
#
# Push order when both changed: fork FIRST (the workspace pins it as a
# submodule — its commit must exist on the public remote before cloning works).
#
# Usage:
#   ./pre-push-fork.sh                 # audit + confirm + push
#   ./pre-push-fork.sh --dry-run       # audit only — no network, no push
#   ./pre-push-fork.sh --yes           # audit + push without prompt
#   ./pre-push-fork.sh --tests         # additionally run tsc + vitest
#   ./pre-push-fork.sh --skip-secret-scan   # only if all hits were false positives
set -euo pipefail
cd "$(dirname "$0")"

REPO_DIR="orthanc-explorer-3-usable"
BASE_REF="${BASE_REF:-origin/main}"
DRY_RUN=0; ASSUME_YES=0; RUN_TESTS=0; SKIP_SECRETS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --tests) RUN_TESTS=1; shift ;;
    --skip-secret-scan) SKIP_SECRETS=1; shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

die() { echo ""; echo "ABORT: $*" >&2; exit 1; }

[ -d "$REPO_DIR/.git" ] || die "$REPO_DIR is not a git repository."
cd "$REPO_DIR"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "── public push audit: $(basename "$(pwd)") ──"
echo "   repo:   $(git remote get-url origin 2>/dev/null || echo '<no origin>')"
echo "   branch: $BRANCH  (base: $BASE_REF)"

# ── 1. remote must be the fork, never upstream ──────────────────────────
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *rhavekost/orthanc-explorer-3*) die "origin points at UPSTREAM ($ORIGIN_URL) — refusing to push." ;;
  *emanuel901z-hue*) : ;;
  "")
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "   WARN: no 'origin' remote yet — audit runs locally, push would need: git remote add origin <url>"
      BASE_REF="$(git rev-parse --abbrev-ref HEAD)~10"  # audit the recent history as a stand-in
      echo "   (dry-run without remote: auditing last 10 commits as base $BASE_REF)"
    else
      die "no 'origin' remote configured — add it first: git remote add origin <url>"
    fi
    ;;
  *) echo "   WARN: origin is not the known owner (emanuel901z-hue) — double-check it." ;;
esac

# ── 2. clean worktree ───────────────────────────────────────────────────
[ -z "$(git status --porcelain)" ] || die "worktree not clean — commit or stash first."

# ── 3. outgoing commits ─────────────────────────────────────────────────
[ "$DRY_RUN" -eq 1 ] || git fetch origin --quiet 2>/dev/null || echo "   WARN: git fetch failed (offline?) — using local $BASE_REF"

COMMITS="$(git log --oneline "$BASE_REF..HEAD" || true)"
[ -n "$COMMITS" ] || { echo "── nothing to push ($BRANCH == $BASE_REF) ──"; exit 0; }

FILES="$(git diff --name-only "$BASE_REF...HEAD")"
echo ""
echo "── outgoing commits (would become public) ──"
echo "$COMMITS" | sed 's/^/   /'
echo ""
echo "── outgoing files ──"
echo "$FILES" | sed 's/^/   /'
echo "   ($(git diff --shortstat "$BASE_REF...HEAD"))"

# ── 4. file blacklist (outgoing diff only) ──────────────────────────────
BLACKLIST='(^|/)\.env($|\.)|\.(db|sqlite|sqlite3)$|\.(pem|key|p12|pfx)$|(^|/)secrets?\.|(^|/)test-results/|(^|/)screenshots/|(^|/)report/|(^|/)node_modules/|(^|/)\.venv/|(^|/)history_[0-9a-f]+\.md$|\.log$'
HITS="$(echo "$FILES" | grep -E "$BLACKLIST" || true)"
[ -z "$HITS" ] || die "blacklisted files in outgoing diff:
$(echo "$HITS" | sed 's/^/   /')"

# ── 5. secret scan over the outgoing diff ───────────────────────────────
if [ "$SKIP_SECRETS" -eq 0 ]; then
  PATTERNS="$(mktemp)"
  trap 'rm -f "$PATTERNS"' EXIT
  cat > "$PATTERNS" <<'PAT'
-----BEGIN [A-Z ]*PRIVATE KEY-----
AKIA[0-9A-Z]{16}
ghp_[A-Za-z0-9]{36}
github_pat_[A-Za-z0-9_]{20,}
sk-[A-Za-z0-9]{20,}
xox[baprs]-[A-Za-z0-9-]{10,}
[Pp]assword["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9!@#$%^&*_+-]{6,}
[Ss]ecret["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9!@#$%^&*_+-]{6,}
[Aa]pi[_-]?[Kk]ey["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9!@#$%^&*_+-]{6,}
PAT
  SECRET_HITS="$(git diff "$BASE_REF...HEAD" | grep -inE -f "$PATTERNS" | grep -viE 'example|placeholder|changeme|super-secret-test-key' || true)"
  [ -z "$SECRET_HITS" ] || die "possible secrets in outgoing diff:
$(echo "$SECRET_HITS" | sed 's/^/   /')
(if these are all false positives: --skip-secret-scan)"
  echo ""
  echo "── secret scan: clean ──"
fi

# ── 6. optional quick checks ────────────────────────────────────────────
if [ "$RUN_TESTS" -eq 1 ]; then
  if [ -f package.json ]; then
    echo ""
    echo "── quick checks (tsc + vitest) ──"
    npx tsc --noEmit -p tsconfig.app.json
    npm run test
  else
    echo ""
    echo "── --tests skipped (no package.json in this repo) ──"
  fi
fi

# ── 7. push ─────────────────────────────────────────────────────────────
echo ""
if [ "$DRY_RUN" -eq 1 ]; then
  echo "── dry-run: all checks passed, nothing pushed ──"
  exit 0
fi

if [ "$ASSUME_YES" -eq 0 ]; then
  read -r -p "Push $BRANCH to origin (public)? [y/N] " answer
  [ "$answer" = "y" ] || [ "$answer" = "Y" ] || { echo "aborted."; exit 1; }
fi

git push origin "$BRANCH"

REPO_PATH="$(echo "$ORIGIN_URL" | sed -E 's#(git@|https://)github.com[:/]##; s#\.git$##')"
echo ""
echo "pushed. open the PR:"
echo "   https://github.com/$REPO_PATH/compare/main...$BRANCH?expand=1"
