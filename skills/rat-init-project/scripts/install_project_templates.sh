#!/usr/bin/env bash
# install_project_templates.sh — bootstrap executable templates into project workspace
# Usage: install_project_templates.sh [--update] [--dry-run] [workspace]
#
# Non-destructive policy (default):
# - Create missing directories
# - Copy template scripts only when destination file does not exist
# - Never overwrite user-modified scripts
#
# With --update:
# - Update only an unchanged managed copy with an older rat-version marker
# - Stage unknown or modified copies under .rat/template-updates for review

set -euo pipefail

UPDATE_MODE=0
DRY_RUN=0
WORKSPACE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) UPDATE_MODE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --help) echo "Usage: $0 [--update] [--dry-run] [workspace]"; exit 0 ;;
    --*) echo "ERROR: unknown option: $1" >&2; exit 2 ;;
    *) [[ -z "$WORKSPACE" ]] || { echo "ERROR: one workspace is required" >&2; exit 2; }; WORKSPACE="$1" ;;
  esac
  shift
done

WORKSPACE="${WORKSPACE:-$(pwd)}"
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
PENDING=0
MANIFEST="$WORKSPACE/.rat/template-hashes.tsv"
MANIFEST_ROWS=""

_content_hash() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum < "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 < "$1" | awk '{print $1}'
  else
    echo "ERROR: sha256sum or shasum is required" >&2
    return 1
  fi
}

_record_hash() {
  MANIFEST_ROWS+="$1"$'\t'"$2"$'\t'"$3"$'\n'
}

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

  if [[ "$DRY_RUN" -eq 0 ]]; then
    mkdir -p "$parent"
  elif [[ ! -d "$parent" ]]; then
    return 0
  fi
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
  local relative="${dst#"$WORKSPACE/"}"
  local src_ver src_hash dst_hash trusted_hash

  [[ -f "$src" ]] || { echo "ERROR: missing template: $src" >&2; return 1; }
  _validate_destination "$dst"
  src_ver=$(_extract_rat_version "$src")
  src_hash=$(_content_hash "$src")
  if [[ -f "$dst" ]]; then
    dst_hash=$(_content_hash "$dst")
    trusted_hash=""
    if [[ -f "$MANIFEST" ]]; then
      trusted_hash=$(awk -F '\t' -v target="$relative" '$1 == target { print $2; exit }' "$MANIFEST")
    fi
    if [[ "$dst_hash" = "$src_hash" ]]; then
      _record_hash "$relative" "$src_hash" "$src_ver"
      SKIPPED=$((SKIPPED + 1))
      return
    fi
    if [[ "$UPDATE_MODE" -eq 1 ]]; then
      local dst_ver
      dst_ver=$(_extract_rat_version "$dst")
      if [[ -n "$trusted_hash" && "$dst_hash" = "$trusted_hash" && -n "$src_ver" && -n "$dst_ver" ]] && \
         _version_gt "$src_ver" "$dst_ver"; then
        if [[ "$DRY_RUN" -eq 0 ]]; then
          local staged
          staged=$(mktemp "${dst}.XXXXXX")
          cp "$src" "$staged"
          chmod "$mode" "$staged"
          mv "$staged" "$dst"
        fi
        _record_hash "$relative" "$src_hash" "$src_ver"
        echo "UPDATE $relative"
        UPDATED=$((UPDATED + 1))
        return
      fi
      if [[ -z "$dst_ver" || -z "$src_ver" ]] || _version_gt "$src_ver" "$dst_ver"; then
        local candidate="$WORKSPACE/.rat/template-updates/$relative"
        _validate_destination "$candidate"
        if [[ "$DRY_RUN" -eq 0 ]]; then
          cp "$src" "$candidate"
          chmod "$mode" "$candidate"
        fi
        echo "REVIEW $relative (existing file preserved)"
        PENDING=$((PENDING + 1))
      fi
    fi
    [[ -z "$trusted_hash" ]] || _record_hash "$relative" "$trusted_hash" "$(_extract_rat_version "$dst")"
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  if [[ "$DRY_RUN" -eq 0 ]]; then
    cp "$src" "$dst"
    chmod "$mode" "$dst"
  fi
  _record_hash "$relative" "$src_hash" "$src_ver"
  echo "CREATE $relative"
  CREATED=$((CREATED + 1))
}

_validate_destination "$MANIFEST"

install_script_if_missing \
  "$PLUGIN_ROOT/scripts/run_sim.sh" \
  "$WORKSPACE/scripts/run_sim.sh" \
  755

install_script_if_missing "$PLUGIN_ROOT/scripts/verify_evidence.py" "$WORKSPACE/lib/verify_evidence.py" 644
install_script_if_missing "$PLUGIN_ROOT/scripts/eda_runner.py" "$WORKSPACE/lib/eda_runner.py" 644
install_script_if_missing "$PLUGIN_ROOT/scripts/eda_setup.py" "$WORKSPACE/lib/eda_setup.py" 644
install_script_if_missing "$PLUGIN_ROOT/scripts/regression_evidence.py" "$WORKSPACE/lib/regression_evidence.py" 644
install_script_if_missing "$PLUGIN_ROOT/scripts/merge_coverpoint_logs.py" "$WORKSPACE/lib/merge_coverpoint_logs.py" 644
install_script_if_missing "$PLUGIN_ROOT/hooks/lib/python-util.sh" "$WORKSPACE/lib/python-util.sh" 644

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

install_script_if_missing "$PLUGIN_ROOT/skills/rat-init-project/templates/Makefile" "$WORKSPACE/Makefile" 644

for rule in rtl-coding-conventions.md rtl-verification-gate.md; do
  if [[ ! -f "$HOME/.claude/rules/$rule" ]]; then
    install_script_if_missing "$PLUGIN_ROOT/skills/rat-init-project/templates/rules/$rule" "$WORKSPACE/.claude/rules/$rule" 644
  fi
done

for dir in rtl sim syn docs reviews refc; do
  install_script_if_missing "$PLUGIN_ROOT/skills/rat-init-project/templates/guides/${dir}-guide.md" "$WORKSPACE/$dir/CLAUDE.md" 644
done

if [[ "$DRY_RUN" -eq 0 ]]; then
  MANIFEST_TMP=$(mktemp "${MANIFEST}.XXXXXX")
  printf '%s' "$MANIFEST_ROWS" > "$MANIFEST_TMP"
  mv "$MANIFEST_TMP" "$MANIFEST"
fi
echo "SETUP_TEMPLATE_INSTALL created=$CREATED updated=$UPDATED skipped=$SKIPPED pending=$PENDING dry_run=$DRY_RUN workspace=$WORKSPACE"
