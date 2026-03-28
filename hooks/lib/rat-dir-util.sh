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

# Check if the given directory is a RAT-initialized RTL project.
# Returns 0 (true) if .rat or .rtl-agent-team exists, 1 otherwise.
rat_is_project() {
  [ -d "$1/.rat" ] || [ -d "$1/.rtl-agent-team" ]
}

# Print the resolved RAT project state directory path.
# Prefers .rat, falls back to .rtl-agent-team.
# Prints nothing and returns 1 if neither exists.
rat_project_dir() {
  if [ -d "$1/.rat" ]; then
    printf '%s' "$1/.rat"
  elif [ -d "$1/.rtl-agent-team" ]; then
    printf '%s' "$1/.rtl-agent-team"
  else
    return 1
  fi
}
