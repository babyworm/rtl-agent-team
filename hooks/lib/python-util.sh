#!/bin/sh
# rat-version: 2.0.0
# Select an interpreter capable of running the shared execution/evidence helpers.

rat_select_python() {
  if [ -n "${RAT_PYTHON:-}" ]; then
    if command -v "$RAT_PYTHON" >/dev/null 2>&1 && "$RAT_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
      printf '%s' "$RAT_PYTHON"
      return 0
    fi
    printf '%s\n' "RAT_PYTHON must name Python >= 3.9: $RAT_PYTHON" >&2
    return 1
  fi
  for _RAT_PY_CANDIDATE in python3 python python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$_RAT_PY_CANDIDATE" >/dev/null 2>&1 && "$_RAT_PY_CANDIDATE" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
      command -v "$_RAT_PY_CANDIDATE"
      return 0
    fi
  done
  printf '%s\n' 'Python >= 3.9 is required; set RAT_PYTHON to its executable.' >&2
  return 1
}
