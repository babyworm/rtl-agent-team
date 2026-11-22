#!/bin/sh
# rat-version: 2.0.1
# Select an interpreter capable of running the shared execution/evidence helpers.
# RAT_PYTHON_MIN is the plugin's Python floor; keep it equal to MIN_PYTHON in
# scripts/rat_compat.py (tests/unit/test_python_compat.py checks both). Python 2 fails
# the probe, so it is never selected.
RAT_PYTHON_MIN=3.9

# True when the interpreter runs and is at least RAT_PYTHON_MIN.
rat_python_ok() {
  "$1" -c 'import sys; floor = tuple(int(part) for part in sys.argv[1].split(".")); sys.exit(tuple(sys.version_info[:2]) < floor)' \
    "$RAT_PYTHON_MIN" >/dev/null 2>&1
}

rat_select_python() {
  if [ -n "${RAT_PYTHON:-}" ]; then
    if command -v "$RAT_PYTHON" >/dev/null 2>&1 && rat_python_ok "$RAT_PYTHON"; then
      printf '%s' "$RAT_PYTHON"
      return 0
    fi
    printf '%s\n' "RAT_PYTHON must name Python >= $RAT_PYTHON_MIN: $RAT_PYTHON" >&2
    return 1
  fi
  for _RAT_PY_CANDIDATE in python3 python python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$_RAT_PY_CANDIDATE" >/dev/null 2>&1 && rat_python_ok "$_RAT_PY_CANDIDATE"; then
      command -v "$_RAT_PY_CANDIDATE"
      return 0
    fi
  done
  printf '%s\n' "Python >= $RAT_PYTHON_MIN is required; set RAT_PYTHON to its executable." >&2
  return 1
}
