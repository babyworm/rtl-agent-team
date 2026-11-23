#!/usr/bin/env bash
# local-ci-check.sh — Run CI-equivalent checks locally before pushing.
#
# Usage: bash scripts/local-ci-check.sh   (or ./scripts/local-ci-check.sh)
#
# Mirrors .github/workflows/ci.yml:
#   1. pytest tests/unit/
#   2. shellcheck on hooks/, scripts/, and skills/
#   3. validate-plugin (template catalog, JSON manifests, version sync, generated files)
#
# Exit code: 0 if all checks pass, 1 if any fail.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FAIL=0
SKIPPED=""

echo "============================================"
echo "  RTL Agent Team — Local CI Check"
echo "============================================"
echo ""

# ── Step 1: Python tests ──────────────────────────────────────────────
echo "[1/3] Running pytest..."

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

echo "  (platform: ${OSTYPE}, bash ${BASH_VERSION} — running full unit suite, CI parity)"

# test_bd_rate.py requires numpy (CI installs via requirements-test.txt)
IGNORE_ARGS="--ignore=tests/unit/test_bd_rate.py"
if python3 -c "import numpy" 2>/dev/null; then
  IGNORE_ARGS=""
else
  echo "  (numpy not installed — skipping test_bd_rate.py; create .venv, then run: .venv/bin/python -m pip install -r tests/requirements-test.txt)"
  SKIPPED="${SKIPPED}numpy "
fi

# shellcheck disable=SC2086
if python3 -m pytest tests/unit/ -x -q $IGNORE_ARGS; then
  echo "  ✓ pytest PASS"
else
  echo "  ✗ pytest FAIL"
  FAIL=1
fi

echo ""

# ── Step 2: shellcheck ────────────────────────────────────────────────
echo "[2/3] Running shellcheck..."

if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -s sh hooks/*.sh && shellcheck -s sh hooks/lib/*.sh; then
    echo "  ✓ shellcheck PASS"
  else
    echo "  ✗ shellcheck FAIL"
    FAIL=1
  fi
else
  echo "  ⚠ shellcheck not installed — skipping (install: apt-get install shellcheck or brew install shellcheck)"
  SKIPPED="${SKIPPED}shellcheck "
fi

echo ""

# ── Step 3: validate-plugin parity ────────────────────────────────────
echo "[3/3] Validating plugin manifests and generated files..."

VALIDATE_OK=1
python3 scripts/template_catalog.py || VALIDATE_OK=0
for f in package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json hooks/hooks.json phase-registry.json skill-completion-criteria.json template-catalog.json .lsp.json; do
  python3 -m json.tool "$f" >/dev/null || VALIDATE_OK=0
done
python3 scripts/sync_agent_policies.py --check || VALIDATE_OK=0
if command -v jq >/dev/null 2>&1; then
  bash scripts/generate-phase-maps.sh --check || VALIDATE_OK=0
else
  echo "  ⚠ jq not installed — skipping generate-phase-maps.sh --check"
  SKIPPED="${SKIPPED}jq "
fi
bash scripts/sync_step0.sh --dry-run >/dev/null || VALIDATE_OK=0
if [ "$VALIDATE_OK" -eq 1 ]; then
  echo "  ✓ validate-plugin PASS"
else
  echo "  ✗ validate-plugin FAIL"
  FAIL=1
fi

echo ""
echo "============================================"
if [ "$FAIL" -eq 0 ]; then
  if [ -n "$SKIPPED" ]; then
    echo "  ✓ CI CHECKS PASSED (skipped: ${SKIPPED% }) — CI will run full suite"
  else
    echo "  ✓ ALL CI CHECKS PASSED — safe to push"
  fi
else
  echo "  ✗ CI CHECKS FAILED — fix before pushing"
fi
echo "============================================"

exit $FAIL
