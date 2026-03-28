#!/bin/sh
# RTL Spawn Context Hook: PreToolUse:TaskCreate
# Refreshes spawn-context.json when an agent is spawned directly via Task()
# without going through a Skill. If TaskCreate is not a valid matcher,
# this hook simply never fires (no harm).

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/spawn-context-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"

jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_continue; }

# Extract subagent_type from tool input.
AGENT_TYPE=$(jsonu_get_input_string "$INPUT" "subagent_type")
[ -z "$AGENT_TYPE" ] && emit_post_continue

# Only handle rtl-agent-team agents.
case "$AGENT_TYPE" in
  rtl-agent-team:*)
    SHORT_NAME="${AGENT_TYPE#rtl-agent-team:}"
    ;;
  *)
    emit_post_continue
    ;;
esac

# Map agent name to corresponding skill name for phase resolution.
# Agent names like "p4-implement-orchestrator" → skill "rtl-p4-implement"
SKILL_NAME=""
case "$SHORT_NAME" in
  # BEGIN GENERATED PHASE_MAP
  # Non-team orchestrators → non-team skills
  p1-research-orchestrator)       SKILL_NAME="p1-spec-research" ;;
  p2-arch-orchestrator)           SKILL_NAME="p2-arch-design" ;;
  p3-uarch-orchestrator)          SKILL_NAME="rtl-p3-uarch-design" ;;
  p4-implement-orchestrator)      SKILL_NAME="rtl-p4-implement" ;;
  p4s-bugfix-orchestrator)        SKILL_NAME="rtl-p4s-bugfix" ;;
  p4s-refactor-orchestrator)      SKILL_NAME="rtl-p4s-refactor" ;;
  p4s-unit-test-orchestrator)     SKILL_NAME="rtl-p4s-unit-test" ;;
  p4-rtl-sanity-orchestrator)     SKILL_NAME="rtl-p4-rapid-impl" ;;
  p4-block-parallel-coordinator)  SKILL_NAME="rtl-p4-block-parallel" ;;
  p5-verify-orchestrator)         SKILL_NAME="rtl-p5-verify" ;;
  p5a-functional-closure-orchestrator) SKILL_NAME="rtl-p5a-functional-closure" ;;
  p5b-silicon-validation-orchestrator) SKILL_NAME="rtl-p5b-silicon-validation" ;;
  p5s-func-verify-orchestrator)   SKILL_NAME="rtl-p5s-func-verify" ;;
  p5s-integration-orchestrator)   SKILL_NAME="rtl-p5s-integration-test" ;;
  p5s-sva-orchestrator)           SKILL_NAME="rtl-p5s-sva-check" ;;
  p5s-cdc-orchestrator)           SKILL_NAME="rtl-p5s-cdc-verify" ;;
  p5s-protocol-orchestrator)      SKILL_NAME="rtl-p5s-protocol-verify" ;;
  p5s-perf-orchestrator)          SKILL_NAME="rtl-p5s-perf-verify" ;;
  p5s-coverage-orchestrator)      SKILL_NAME="rtl-p5s-coverage-analyze" ;;
  p5s-uvm-orchestrator)           SKILL_NAME="rtl-p5s-uvm-verify" ;;
  p6-review-orchestrator)         SKILL_NAME="rtl-p6-design-review" ;;
  p7-exploration-orchestrator)    SKILL_NAME="rtl-p7-exploration" ;;
  review-refactor-orchestrator)   SKILL_NAME="rtl-review-refactor" ;;
  autopilot-orchestrator)         SKILL_NAME="rat-auto-design" ;;
  spec-to-uarch-orchestrator)     SKILL_NAME="rat-p1p3-spec-uarch" ;;
  uarch-to-verify-orchestrator)   SKILL_NAME="rat-p4p5-impl-verify" ;;
  dse-orchestrator)               SKILL_NAME="rat-dse" ;;
  # Team orchestrators → team skills (1:1 mapping)
  p1-research-team-orchestrator)  SKILL_NAME="rtl-p1-research-team" ;;
  p2-arch-team-orchestrator)      SKILL_NAME="rtl-p2-arch-team" ;;
  p3-uarch-team-orchestrator)     SKILL_NAME="rtl-p3-uarch-team" ;;
  p4-implement-team-orchestrator) SKILL_NAME="rtl-p4-implement-team" ;;
  p5-verify-team-orchestrator)    SKILL_NAME="rtl-p5-verify-team" ;;
  spec-to-uarch-team-orchestrator) SKILL_NAME="rat-p1p3-spec-uarch-team" ;;
  # END GENERATED PHASE_MAP
  *)
    emit_post_continue
    ;;
esac

# Always write/overwrite manifest to ensure phase/skill context is current.
if [ -n "$SKILL_NAME" ]; then
  sctx_write_manifest "$CWD" "$SKILL_NAME"
fi

# Audit: log spawn_start event
_AUDIT_LIB="$SCRIPT_DIR/lib/audit-util.sh"
if [ -f "$_AUDIT_LIB" ]; then
  . "$SCRIPT_DIR/lib/flock-util.sh"
  . "$_AUDIT_LIB"
  _AUDIT_SID=$(audit_session_id "$CWD")
  if [ -n "$_AUDIT_SID" ] && [ -d "$RAT_DIR/audit/$_AUDIT_SID" ]; then
    _AUDIT_PHASE=$(sctx_skill_to_phase "$SKILL_NAME")
    [ -z "$_AUDIT_PHASE" ] && _AUDIT_PHASE="null"
    _AUDIT_SAFE_AGENT=$(jsonu_escape "$SHORT_NAME")
    _AUDIT_SAFE_SKILL=$(jsonu_escape "$SKILL_NAME")
    _AUDIT_SEQ=$(audit_trace_append "$CWD" \
      "{\"event\":\"spawn_start\",\"agent\":\"${_AUDIT_SAFE_AGENT}\",\"phase\":${_AUDIT_PHASE},\"detail\":\"Spawning ${_AUDIT_SAFE_AGENT} via ${_AUDIT_SAFE_SKILL}\",\"status\":\"started\"}")

    # Attempt to capture prompt from stdin (may not be available)
    _AUDIT_PROMPT=$(jsonu_get_input_string "$INPUT" "prompt")
    if [ -n "$_AUDIT_PROMPT" ]; then
      audit_save_prompt "$CWD" "$_AUDIT_SEQ" "$SHORT_NAME" "$_AUDIT_PROMPT"
    fi
  fi
fi

emit_post_continue
