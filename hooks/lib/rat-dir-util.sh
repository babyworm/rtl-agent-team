#!/bin/sh
# rat-dir-util.sh — POSIX sh utility to resolve the RAT project state directory.
#
# Primary directory: .rat (v0.8.12+)
# Legacy fallback:   .rtl-agent-team (v0.8.11 and earlier)
#
# Usage:
#   . "$SCRIPT_DIR/lib/rat-dir-util.sh"
#   if rat_is_project "$CWD"; then
#     RAT_DIR=$(rat_project_dir "$CWD")
#   fi

# Optional override: when RAT_PROJECT_ROOT is set AND points at an existing
# directory, it replaces the caller-supplied directory for the marker check.
# This lets an external driver (e.g. a Workflow orchestrator whose subagents
# default to a different CWD) point all hooks at the real project root.
# When RAT_PROJECT_ROOT is unset, empty, OR not a directory, behavior falls back
# to the legacy CWD-based logic UNCHANGED, so this is fully backward-compatible.
# The existence contract (return 1 when no marker) is preserved: if an overriding
# RAT_PROJECT_ROOT directory has no .rat/.rtl-agent-team marker, resolution still
# fails exactly as before. The `-d` guard is set -u safe (${..:-}) and set -e
# safe (AND-OR non-final exemption; matches the existing `[ -z "$CWD" ] && ...`
# idiom).

# Check if the given directory is a RAT-initialized RTL project.
# Returns 0 (true) if .rat or .rtl-agent-team exists, 1 otherwise.
rat_is_project() {
  [ -d "${RAT_PROJECT_ROOT:-}" ] && set -- "$RAT_PROJECT_ROOT"
  [ -d "$1/.rat" ] || [ -d "$1/.rtl-agent-team" ]
}

# Print the resolved RAT project state directory path.
# Prefers .rat, falls back to .rtl-agent-team.
# Prints nothing and returns 1 if neither exists.
rat_project_dir() {
  [ -d "${RAT_PROJECT_ROOT:-}" ] && set -- "$RAT_PROJECT_ROOT"
  if [ -d "$1/.rat" ]; then
    printf '%s' "$1/.rat"
  elif [ -d "$1/.rtl-agent-team" ]; then
    printf '%s' "$1/.rtl-agent-team"
  else
    return 1
  fi
}
