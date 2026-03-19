#!/usr/bin/env bash
# local-ci-check.sh — Run CI-equivalent checks locally before pushing.
#
# Usage: bash scripts/local-ci-check.sh   (or ./scripts/local-ci-check.sh)
#
# Mirrors .github/workflows/ci.yml:
#   1. pytest tests/unit/
#   2. shellcheck -s sh hooks/*.sh hooks/lib/*.sh
#
# On macOS or bash < 5, tests requiring Ubuntu bash 5+ / specific binaries
# are automatically deselected. On Linux with bash 5+, all tests run (CI parity).
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

# Platform detection: skip shell-execution tests only on macOS or bash < 5
# On Linux with bash 5+ (CI environment), run everything for full parity
DESELECT_ARGS=""
if [[ "$OSTYPE" == darwin* ]] || [[ "${BASH_VERSINFO[0]}" -lt 5 ]]; then
  echo "  (platform: ${OSTYPE}, bash ${BASH_VERSION} — deselecting shell-execution tests)"
  SKIP_MARKERS=(
    "tests/unit/test_hooks.py::TestSessionScopedState"       # hook subprocess: depends on Linux shell tools (json-util.sh sed patterns)
    "tests/unit/test_hooks.py::TestSkillCompletionGate"      # hook subprocess: depends on Linux shell tools (json-util.sh sed patterns)
    "tests/unit/test_hooks.py::TestHookConcurrency"          # concurrent hook subprocess: mkdir-based locking timing varies across platforms
    "tests/unit/test_hooks.py::TestTeamAwarenessGuard"       # hook subprocess: depends on Linux shell tools (team-gate-util.sh)
    "tests/unit/test_hooks.py::TestSedFallbackContract"      # requires GNU sed behavior (BSD sed incompatible)
    "tests/unit/test_plugin_runtime_contract.py::TestSystemVerilogLspPluginContract"  # shell subprocess: install script uses GNU sort -V
    "tests/unit/test_regression_coverage.py::TestRunRegression"  # shell subprocess: run_regression.sh uses declare -A (bash 4+) + nproc
  )
  for marker in "${SKIP_MARKERS[@]}"; do
    DESELECT_ARGS="$DESELECT_ARGS --deselect=$marker"
  done
else
  echo "  (platform: ${OSTYPE}, bash ${BASH_VERSION} — running all tests, CI parity)"
fi

# test_bd_rate.py requires numpy (CI installs via requirements-test.txt)
IGNORE_ARGS="--ignore=tests/unit/test_bd_rate.py"
if python3 -c "import numpy" 2>/dev/null; then
  IGNORE_ARGS=""
fi

# shellcheck disable=SC2086
if python3 -m pytest tests/unit/ -x -q $IGNORE_ARGS $DESELECT_ARGS; then
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
  echo "  ⚠ shellcheck not installed — skipping (install: apt-get install shellcheck or brew install shellcheck)"
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
