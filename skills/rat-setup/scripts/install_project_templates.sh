#!/usr/bin/env bash
# install_project_templates.sh — bootstrap executable templates into project workspace
# Usage: install_project_templates.sh [--update] [workspace]
#
# Non-destructive policy (default):
# - Create missing directories
# - Copy template scripts only when destination file does not exist
# - Never overwrite user-modified scripts
#
# With --update:
# - Overwrite destination if source has a newer rat-version marker
# - Files without version markers are never overwritten

set -euo pipefail

UPDATE_MODE=0
if [[ "${1:-}" = "--update" ]]; then
  UPDATE_MODE=1
  shift
fi

WORKSPACE="${1:-$(pwd)}"
if [[ ! -d "$WORKSPACE" ]]; then
  echo "ERROR: workspace directory does not exist: $WORKSPACE" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CREATED=0
SKIPPED=0
UPDATED=0

# Extract rat-version marker from a file. Returns empty if not found.
_extract_rat_version() {
  grep -o 'rat-version: [0-9.]*' "$1" 2>/dev/null | head -n1 | sed 's/rat-version: //' || true
}

install_script_if_missing() {
  local src="$1"
  local dst="$2"
  local mode="${3:-755}"

  mkdir -p "$(dirname "$dst")"
  if [[ -f "$dst" ]]; then
    if [[ "$UPDATE_MODE" -eq 1 ]]; then
      local src_ver dst_ver
      src_ver=$(_extract_rat_version "$src")
      dst_ver=$(_extract_rat_version "$dst")
      if [[ -n "$src_ver" && -n "$dst_ver" && "$src_ver" != "$dst_ver" ]]; then
        cp "$src" "$dst"
        chmod "$mode" "$dst"
        UPDATED=$((UPDATED + 1))
        return
      fi
    fi
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  cp "$src" "$dst"
  chmod "$mode" "$dst"
  CREATED=$((CREATED + 1))
}

install_script_if_missing \
  "$PLUGIN_ROOT/scripts/run_sim.sh" \
  "$WORKSPACE/scripts/run_sim.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-setup/templates/run_lint.sh" \
  "$WORKSPACE/lint/scripts/run_lint.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-setup/templates/run_syn.sh" \
  "$WORKSPACE/syn/scripts/run_syn.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-setup/templates/run_cdc.sh" \
  "$WORKSPACE/sim/cdc/run_cdc.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-setup/templates/lib/tool-runner.sh" \
  "$WORKSPACE/lib/tool-runner.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-setup/templates/run_formality.sh" \
  "$WORKSPACE/syn/scripts/run_formality.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-setup/templates/run_conformal.sh" \
  "$WORKSPACE/syn/scripts/run_conformal.sh" \
  755

echo "SETUP_TEMPLATE_INSTALL created=$CREATED updated=$UPDATED skipped=$SKIPPED workspace=$WORKSPACE"
