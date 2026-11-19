#!/usr/bin/env bash
# Read-only readiness for a requested phase; installation does not require all EDA tools.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../hooks/lib/python-util.sh"
RAT_PYTHON=$(rat_select_python)
export RAT_PYTHON
PROJECT_ROOT="${RAT_PROJECT_ROOT:-$PWD}"
PHASE="${1:-${RAT_SETUP_PHASE:-p1}}"
printf 'RAT environment check, scope=%s (use p4/p5a/p5b/all for EDA readiness)\n' "$PHASE"
"$RAT_PYTHON" "$SCRIPT_DIR/eda_runner.py" capabilities --root "$PROJECT_ROOT" --phase "$PHASE"
