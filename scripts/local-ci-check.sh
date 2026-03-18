#!/usr/bin/env bash
# local-ci-check.sh — Run CI-equivalent checks locally before pushing.
#
# Usage: sh scripts/local-ci-check.sh
#
# Mirrors .github/workflows/ci.yml:
#   1. pytest tests/unit/ (skips macOS-incompatible shell execution tests)
#   2. shellcheck -s sh hooks/*.sh hooks/lib/*.sh
#
# Exit code: 0 if all checks pass, 1 if any fail.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FAIL=0

echo "============================================"
echo "  RTL Agent Team — Local CI Check"
echo "============================================"
echo ""

# ── Step 1: Python tests ──────────────────────────────────────────────
echo "[1/2] Running pytest..."

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

# Skip tests that require Ubuntu bash 5+ or specific binaries
SKIP_MARKERS=(
  "tests/unit/test_hooks.py::TestSessionScopedState"
  "tests/unit/test_hooks.py::TestSkillCompletionGate"
  "tests/unit/test_hooks.py::TestHookConcurrency"
  "tests/unit/test_hooks.py::TestTeamAwarenessGuard"
  "tests/unit/test_hooks.py::TestSedFallbackContract"
  "tests/unit/test_plugin_runtime_contract.py::TestSystemVerilogLspPluginContract"
  "tests/unit/test_regression_coverage.py::TestRunRegression"
)

DESELECT_ARGS=""
for marker in "${SKIP_MARKERS[@]}"; do
  DESELECT_ARGS="$DESELECT_ARGS --deselect=$marker"
done

# shellcheck disable=SC2086
if python3 -m pytest tests/unit/ -x -q $DESELECT_ARGS; then
  echo "  ✓ pytest PASS"
else
  echo "  ✗ pytest FAIL"
  FAIL=1
fi

echo ""

# ── Step 2: shellcheck ────────────────────────────────────────────────
echo "[2/2] Running shellcheck..."

if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -s sh hooks/*.sh && shellcheck -s sh hooks/lib/*.sh; then
    echo "  ✓ shellcheck PASS"
  else
    echo "  ✗ shellcheck FAIL"
    FAIL=1
  fi
else
  echo "  ⚠ shellcheck not installed — skipping (install: brew install shellcheck)"
fi

echo ""
echo "============================================"
if [ "$FAIL" -eq 0 ]; then
  echo "  ✓ ALL CI CHECKS PASSED — safe to push"
else
  echo "  ✗ CI CHECKS FAILED — fix before pushing"
fi
echo "============================================"

exit $FAIL
