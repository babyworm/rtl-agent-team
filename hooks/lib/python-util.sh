#!/bin/sh
# rat-version: 1.0.0
# Select an interpreter capable of running the shared execution/evidence helpers.
# RAT_PYTHON_MIN is the plugin's Python floor; keep it equal to MIN_PYTHON in
# scripts/rat_compat.py (tests/unit/test_python_compat.py checks both). Python 2 fails
# the probe, so it is never selected.
RAT_PYTHON_MIN=3.9

# Without the developer tools, macOS /usr/bin/python3 is a shim that opens an install dialog
# when run; a hook must never start it. True when $1 is that shim (compared as a file, so
# /usr//bin or a symlink to it count too) and the selected developer folder has no python3.
# -ef is in dash, bash, busybox, ksh and zsh (POSIX.1-2024); older shellcheck flags it.
rat_python_stub() {
  # shellcheck disable=SC3013
  [ "$1" -ef /usr/bin/python3 ] || return 1
  [ "$(uname -s 2>/dev/null || /usr/bin/uname -s 2>/dev/null)" = Darwin ] || return 1
  # The selected developer folder must hold its own python3, not point back at the shim
  # (an empty or "/" answer from xcode-select would otherwise name the shim itself).
  _rps_dir=$(xcode-select -p 2>/dev/null) || return 0
  # shellcheck disable=SC3013
  [ -x "$_rps_dir/usr/bin/python3" ] && ! [ "$_rps_dir/usr/bin/python3" -ef /usr/bin/python3 ] && return 1
  return 0
}

# True when the interpreter runs and is at least RAT_PYTHON_MIN.
rat_python_ok() {
  _rpo_path=$(command -v "$1" 2>/dev/null) || return 1
  rat_python_stub "$_rpo_path" && return 1
  "$_rpo_path" -c 'import sys; floor = tuple(int(part) for part in sys.argv[1].split(".")); sys.exit(tuple(sys.version_info[:2]) < floor)' \
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
