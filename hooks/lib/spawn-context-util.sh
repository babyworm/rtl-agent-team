#!/bin/sh
# Spawn Context Manifest writer for agent context handoff.
# Writes .rtl-agent-team/state/spawn-context.json with setup, pipeline,
# upstream artifact, staleness, team, and quality gate information.
#
# Requires: json-util.sh sourced and parser detected.
# Usage:
#   . "$SCRIPT_DIR/lib/spawn-context-util.sh"
#   sctx_write_manifest "$CWD" "$SHORT_SKILL_NAME"

# SCRIPT_DIR is set by the parent hook before sourcing this file.
_SCTX_LIB_DIR="${SCRIPT_DIR:-.}/lib"
. "$_SCTX_LIB_DIR/artifact-map.sh"

# Map skill short name to phase number.
sctx_skill_to_phase() {
  case "$1" in
    p1-spec-research|rtl-p1-research-team) echo 1 ;;
    p2-arch-design|rtl-p2-arch-team)       echo 2 ;;
    rtl-p3-uarch-design|rtl-p3-uarch-team) echo 3 ;;
    rtl-p4-implement|rtl-p4-implement-team|rtl-p4s-bugfix|rtl-p4s-unit-test|rtl-p4s-refactor|rtl-p4-rapid-impl|rtl-review-refactor) echo 4 ;;
    rtl-p5-verify|rtl-p5-verify-team|rtl-p5s-func-verify|rtl-p5s-integration-test|rtl-p5a-functional-closure|rtl-p5b-silicon-validation) echo 5 ;;
    rtl-p5s-sva-check|rtl-p5s-cdc-verify|rtl-p5s-protocol-verify|rtl-p5s-perf-verify|rtl-p5s-coverage-analyze|rtl-p5s-uvm-verify) echo 5 ;;
    rtl-p6-design-review) echo 6 ;;
    rtl-autopilot|rtl-spec-to-uarch|rtl-spec-to-uarch-team|rtl-dse) echo 1 ;;
    rtl-uarch-to-verify) echo 4 ;;
    *) echo "" ;;
  esac
}

# Get mtime as epoch seconds. Empty string if file/dir not found.
_sctx_mtime() {
  [ ! -e "$1" ] && return 0
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || printf ''
}

# Build a JSON artifact entry: {"path":"...","exists":bool,"mtime_epoch":N,"role":"..."}
_sctx_artifact_entry() {
  _ART_REL="$1"
  _ART_ROLE="$2"
  _ART_CWD="$3"
  _ART_FULL="$_ART_CWD/$_ART_REL"

  if [ -e "$_ART_FULL" ]; then
    _ART_EXISTS="true"
    _ART_MTIME=$(_sctx_mtime "$_ART_FULL")
    [ -z "$_ART_MTIME" ] && _ART_MTIME=0
  else
    _ART_EXISTS="false"
    _ART_MTIME=0
  fi

  printf '{"path":"%s","exists":%s,"mtime_epoch":%s,"role":"%s"}' \
    "$_ART_REL" "$_ART_EXISTS" "$_ART_MTIME" "$_ART_ROLE"
}

# Build JSON array of artifact entries from artmap output.
# Usage: _sctx_build_artifact_array "$CWD" "required" "$PHASE"
_sctx_build_artifact_array() {
  _BA_CWD="$1"
  _BA_TYPE="$2"
  _BA_PHASE="$3"
  _BA_FIRST=1
  _BA_ALL_PRESENT=1

  printf '['
  if [ "$_BA_TYPE" = "required" ]; then
    _BA_LINES=$(artmap_required "$_BA_PHASE")
  else
    _BA_LINES=$(artmap_optional "$_BA_PHASE")
  fi

  if [ -n "$_BA_LINES" ]; then
    echo "$_BA_LINES" | while IFS='|' read -r _ba_path _ba_role; do
      [ -z "$_ba_path" ] && continue
      if [ "$_BA_FIRST" -eq 1 ]; then
        _BA_FIRST=0
      else
        printf ','
      fi
      _sctx_artifact_entry "$_ba_path" "$_ba_role" "$_BA_CWD"
    done
  fi
  printf ']'
}

# Check if all required artifacts are present. Returns "true" or "false".
_sctx_all_required_present() {
  _ARP_CWD="$1"
  _ARP_PHASE="$2"
  _ARP_LINES=$(artmap_required "$_ARP_PHASE")

  if [ -z "$_ARP_LINES" ]; then
    echo "true"
    return 0
  fi

  # Avoid pipe subshell — use here-document so variable mutation persists.
  _ARP_RESULT="true"
  while IFS='|' read -r _arp_path _arp_role; do
    [ -z "$_arp_path" ] && continue
    if [ ! -e "$_ARP_CWD/$_arp_path" ]; then
      _ARP_RESULT="false"
      break
    fi
  done <<ARP_EOF
$_ARP_LINES
ARP_EOF

  echo "$_ARP_RESULT"
}

# Collect staleness information.
_sctx_staleness_json() {
  _ST_CWD="$1"
  _ST_STATE="$_ST_CWD/.rtl-agent-team/state"
  _ST_TRACK="$_ST_STATE/rtl-modified-files.txt"

  _ST_COUNT=0
  if [ -f "$_ST_TRACK" ] && [ -s "$_ST_TRACK" ]; then
    _ST_COUNT=$(wc -l < "$_ST_TRACK" | tr -d ' ')
  fi

  _ST_VERIFY="false"
  if [ -f "$_ST_STATE/rtl-verify-done" ] || [ -f "$_ST_STATE/rtl-verify-waiver" ]; then
    _ST_VERIFY="true"
  fi

  _ST_P6_STALE="false"
  if [ -f "$_ST_STATE/p6-stale" ]; then
    _ST_P6_STALE="true"
  fi

  printf '{"rtl_modified_count":%s,"rtl_verify_done":%s,"phase6_stale":%s}' \
    "$_ST_COUNT" "$_ST_VERIFY" "$_ST_P6_STALE"
}

# Collect team mode information.
_sctx_team_json() {
  _TM_CWD="$1"
  _TM_CONFIG="$_TM_CWD/.rtl-agent-team/state/team-config.json"

  if [ ! -f "$_TM_CONFIG" ]; then
    printf '{"active":false,"leader_session_id":""}'
    return 0
  fi

  _TM_ACTIVE=$(jsonu_get_file_path_bool "$_TM_CONFIG" "team_mode")
  [ "$_TM_ACTIVE" != "true" ] && _TM_ACTIVE="false"

  _TM_LEADER=$(jsonu_get_file_path_string "$_TM_CONFIG" "leader_session_id")
  [ -z "$_TM_LEADER" ] && _TM_LEADER=""

  printf '{"active":%s,"leader_session_id":"%s"}' "$_TM_ACTIVE" "$_TM_LEADER"
}

# Collect quality gate status.
_sctx_quality_gates_json() {
  _QG_CWD="$1"

  _QG_P1="false"
  [ -f "$_QG_CWD/docs/phase-1-research/requirements.json" ] && _QG_P1="true"

  _QG_P2="false"
  [ -f "$_QG_CWD/docs/phase-2-architecture/architecture.md" ] && _QG_P2="true"

  _QG_P3="false"
  if [ -d "$_QG_CWD/docs/phase-3-uarch" ]; then
    _QG_P3_COUNT=$(find "$_QG_CWD/docs/phase-3-uarch" -maxdepth 1 -name '*.md' 2>/dev/null | head -n 1)
    [ -n "$_QG_P3_COUNT" ] && _QG_P3="true"
  fi

  _QG_P4="false"
  if [ -d "$_QG_CWD/rtl" ]; then
    _QG_P4_COUNT=$(find "$_QG_CWD/rtl" -name '*.sv' 2>/dev/null | head -n 1)
    [ -n "$_QG_P4_COUNT" ] && _QG_P4="true"
  fi

  _QG_P5A="null"
  _QG_P5A_STATE="$_QG_CWD/.rtl-agent-team/state/p5a-state.json"
  if [ -f "$_QG_P5A_STATE" ]; then
    _QG_P5A_RAW=$(jsonu_get_file_path_string "$_QG_P5A_STATE" "gates.p5a_exit.verdict")
    if [ -n "$_QG_P5A_RAW" ]; then
      _QG_P5A="\"$_QG_P5A_RAW\""
    fi
  fi

  printf '{"p1_passed":%s,"p2_passed":%s,"p3_passed":%s,"p4_passed":%s,"p5a_verdict":%s}' \
    "$_QG_P1" "$_QG_P2" "$_QG_P3" "$_QG_P4" "$_QG_P5A"
}

# Main entry point: write spawn context manifest.
# sctx_write_manifest <cwd> <skill_short_name>
# Returns: 0 on success (manifest written), 1 on skip (no phase mapping, no refresh needed)
sctx_write_manifest() {
  SCTX_CWD="$1"
  SCTX_SKILL="$2"
  SCTX_MANIFEST="$SCTX_CWD/.rtl-agent-team/state/spawn-context.json"

  SCTX_PHASE=$(sctx_skill_to_phase "$SCTX_SKILL")
  if [ -z "$SCTX_PHASE" ]; then
    # No direct phase mapping. If skill is rtl-setup and a manifest exists,
    # refresh it using the previously stored skill context (setup marker may have changed).
    if [ "$SCTX_SKILL" = "rtl-setup" ] && [ -f "$SCTX_MANIFEST" ]; then
      _PREV_SKILL=$(jsonu_get_file_path_string "$SCTX_MANIFEST" "pipeline.skill_invoked")
      if [ -n "$_PREV_SKILL" ]; then
        SCTX_SKILL="$_PREV_SKILL"
        SCTX_PHASE=$(sctx_skill_to_phase "$SCTX_SKILL")
      fi
    fi
    if [ -z "$SCTX_PHASE" ]; then
      return 1
    fi
  fi

  # Setup check
  SCTX_SETUP="false"
  SCTX_MARKER=".claude/rules/rtl-coding-conventions.md"
  if [ -f "$SCTX_CWD/$SCTX_MARKER" ]; then
    SCTX_SETUP="true"
  fi

  # Timestamp
  SCTX_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)

  # Artifact arrays
  SCTX_REQ=$(_sctx_build_artifact_array "$SCTX_CWD" "required" "$SCTX_PHASE")
  SCTX_OPT=$(_sctx_build_artifact_array "$SCTX_CWD" "optional" "$SCTX_PHASE")

  # All required present check — run in main shell to capture output
  SCTX_ALL_PRESENT=$(_sctx_all_required_present "$SCTX_CWD" "$SCTX_PHASE" | tail -n 1)
  [ -z "$SCTX_ALL_PRESENT" ] && SCTX_ALL_PRESENT="true"

  # Staleness
  SCTX_STALE=$(_sctx_staleness_json "$SCTX_CWD")

  # Team
  SCTX_TEAM=$(_sctx_team_json "$SCTX_CWD")

  # Quality gates
  SCTX_GATES=$(_sctx_quality_gates_json "$SCTX_CWD")

  # Atomic write
  mkdir -p "$(dirname "$SCTX_MANIFEST")"
  cat > "$SCTX_MANIFEST.tmp" <<MANIFEST_EOF
{"schema_version":"1.0","generated_at":"$SCTX_TS","generated_by":"rtl-phase-state-bootstrap.sh","setup":{"completed":$SCTX_SETUP,"marker":"$SCTX_MARKER"},"pipeline":{"current_phase":$SCTX_PHASE,"skill_invoked":"$SCTX_SKILL"},"upstream_artifacts":{"required":$SCTX_REQ,"optional":$SCTX_OPT,"all_required_present":$SCTX_ALL_PRESENT},"staleness":$SCTX_STALE,"team":$SCTX_TEAM,"quality_gates":$SCTX_GATES}
MANIFEST_EOF
  mv "$SCTX_MANIFEST.tmp" "$SCTX_MANIFEST"
}

# Return a 1-line summary for additionalContext.
# Reads from the written manifest to ensure accuracy (handles rtl-setup refresh case).
sctx_summary() {
  SCTX_S_CWD="$1"
  SCTX_S_MANIFEST="$SCTX_S_CWD/.rtl-agent-team/state/spawn-context.json"

  if [ ! -f "$SCTX_S_MANIFEST" ]; then
    return 1
  fi

  _S_PHASE=$(jsonu_get_file_path_num "$SCTX_S_MANIFEST" "pipeline.current_phase")
  [ -z "$_S_PHASE" ] && _S_PHASE="?"

  _S_SETUP_VAL=$(jsonu_get_file_path_bool "$SCTX_S_MANIFEST" "setup.completed")
  _S_SETUP="OK"
  [ "$_S_SETUP_VAL" != "true" ] && _S_SETUP="MISSING"

  _S_ARP_VAL=$(jsonu_get_file_path_bool "$SCTX_S_MANIFEST" "upstream_artifacts.all_required_present")
  _S_ART="ALL_PRESENT"
  [ "$_S_ARP_VAL" != "true" ] && _S_ART="INCOMPLETE"

  printf '[Spawn Context] Phase %s, setup=%s, upstream=%s, manifest written' \
    "$_S_PHASE" "$_S_SETUP" "$_S_ART"
}
