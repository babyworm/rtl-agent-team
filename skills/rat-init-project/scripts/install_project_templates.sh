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
WORKSPACE="$(cd "$WORKSPACE" && pwd -P)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CREATED=0
SKIPPED=0
UPDATED=0

# Extract rat-version marker from a file. Returns empty if not found.
_extract_rat_version() {
  awk 'match($0, /rat-version: [0-9.]+/) {
    value = substr($0, RSTART, RLENGTH)
    sub(/^rat-version: /, "", value)
    print value
    exit
  }' "$1" 2>/dev/null || true
}

_version_gt() {
  awk -v candidate="$1" -v installed="$2" 'BEGIN {
    candidate_count = split(candidate, candidate_parts, ".")
    installed_count = split(installed, installed_parts, ".")
    part_count = candidate_count > installed_count ? candidate_count : installed_count
    for (part_index = 1; part_index <= part_count; part_index++) {
      candidate_part = part_index <= candidate_count ? candidate_parts[part_index] + 0 : 0
      installed_part = part_index <= installed_count ? installed_parts[part_index] + 0 : 0
      if (candidate_part > installed_part) exit 0
      if (candidate_part < installed_part) exit 1
    }
    exit 1
  }'
}

_validate_destination() {
  local dst="$1"
  local parent existing resolved

  if [[ -L "$dst" ]]; then
    echo "ERROR: refusing symlink template destination: $dst" >&2
    return 1
  fi

  parent=$(dirname "$dst")
  existing="$parent"
  while [[ ! -d "$existing" ]]; do
    if [[ -e "$existing" || -L "$existing" ]]; then
      echo "ERROR: template destination parent is not a directory: $existing" >&2
      return 1
    fi
    existing=$(dirname "$existing")
  done

  resolved=$(cd "$existing" && pwd -P)
  case "$resolved/" in
    "$WORKSPACE/"*) ;;
    *)
      echo "ERROR: template destination escapes workspace: $dst" >&2
      return 1
      ;;
  esac

  mkdir -p "$parent"
  resolved=$(cd "$parent" && pwd -P)
  case "$resolved/" in
    "$WORKSPACE/"*) ;;
    *)
      echo "ERROR: template destination escapes workspace: $dst" >&2
      return 1
      ;;
  esac

  if [[ -L "$dst" || ( -e "$dst" && ! -f "$dst" ) ]]; then
    echo "ERROR: template destination is not a regular file: $dst" >&2
    return 1
  fi
  if [[ -f "$dst" ]] && \
     [[ -n "$(find "$dst" -type f ! -links 1 -print -quit 2>/dev/null)" ]]; then
    echo "ERROR: refusing hard-linked template destination: $dst" >&2
    return 1
  fi
}

install_script_if_missing() {
  local src="$1"
  local dst="$2"
  local mode="${3:-755}"

  _validate_destination "$dst"
  if [[ -f "$dst" ]]; then
    if [[ "$UPDATE_MODE" -eq 1 ]]; then
      local src_ver dst_ver
      src_ver=$(_extract_rat_version "$src")
      dst_ver=$(_extract_rat_version "$dst")
      if [[ -n "$src_ver" && -n "$dst_ver" && "$src_ver" != "$dst_ver" ]] && \
         _version_gt "$src_ver" "$dst_ver"; then
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
  "$PLUGIN_ROOT/skills/rat-init-project/templates/run_lint.sh" \
  "$WORKSPACE/lint/scripts/run_lint.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-init-project/templates/run_syn.sh" \
  "$WORKSPACE/syn/scripts/run_syn.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-init-project/templates/run_cdc.sh" \
  "$WORKSPACE/lint/scripts/run_cdc.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-init-project/templates/lib/tool-runner.sh" \
  "$WORKSPACE/lib/tool-runner.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-init-project/templates/run_formality.sh" \
  "$WORKSPACE/syn/scripts/run_formality.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rat-init-project/templates/run_conformal.sh" \
  "$WORKSPACE/syn/scripts/run_conformal.sh" \
  755

install_script_if_missing \
  "$PLUGIN_ROOT/skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh" \
  "$WORKSPACE/sim/uvm/scripts/run_regression_uvm.sh" \
  755

echo "SETUP_TEMPLATE_INSTALL created=$CREATED updated=$UPDATED skipped=$SKIPPED workspace=$WORKSPACE"
