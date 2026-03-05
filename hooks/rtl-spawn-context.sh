#!/bin/sh
# RTL Spawn Context Hook: PreToolUse:TaskCreate (EXPERIMENTAL)
# Refreshes spawn-context.json when an agent is spawned directly via Task()
# without going through a Skill. If TaskCreate is not a valid matcher,
# this hook simply never fires (no harm).

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/spawn-context-util.sh"

jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

# Extract subagent_type from tool input.
AGENT_TYPE=$(jsonu_get_input_string "$INPUT" "subagent_type")
[ -z "$AGENT_TYPE" ] && printf '{"continue":true}' && exit 0

# Only handle rtl-agent-team agents.
case "$AGENT_TYPE" in
  rtl-agent-team:*)
    SHORT_NAME="${AGENT_TYPE#rtl-agent-team:}"
    ;;
  *)
    printf '{"continue":true}'
    exit 0
    ;;
esac

# Map agent name to corresponding skill name for phase resolution.
# Agent names like "p4-implement-orchestrator" → skill "rtl-p4-implement"
SKILL_NAME=""
case "$SHORT_NAME" in
  # Non-team orchestrators → non-team skills
  p1-research-orchestrator)       SKILL_NAME="p1-spec-research" ;;
  p2-arch-orchestrator)           SKILL_NAME="p2-arch-design" ;;
  p3-uarch-orchestrator)          SKILL_NAME="rtl-p3-uarch-design" ;;
  p4-implement-orchestrator)      SKILL_NAME="rtl-p4-implement" ;;
  p4s-bugfix-orchestrator)        SKILL_NAME="rtl-p4s-bugfix" ;;
  p4s-unit-test-orchestrator)     SKILL_NAME="rtl-p4s-unit-test" ;;
  p5-verify-orchestrator)         SKILL_NAME="rtl-p5-verify" ;;
  p5s-func-verify-orchestrator)   SKILL_NAME="rtl-p5s-func-verify" ;;
  p5s-integration-orchestrator)   SKILL_NAME="rtl-p5s-integration-test" ;;
  p6-review-orchestrator)         SKILL_NAME="rtl-p6-design-review" ;;
  autopilot-orchestrator)         SKILL_NAME="rtl-autopilot" ;;
  spec-to-uarch-orchestrator)     SKILL_NAME="rtl-spec-to-uarch" ;;
  uarch-to-verify-orchestrator)   SKILL_NAME="rtl-uarch-to-verify" ;;
  dse-orchestrator)               SKILL_NAME="rtl-dse" ;;
  # Team orchestrators → team skills (1:1 mapping)
  p1-research-team-orchestrator)  SKILL_NAME="rtl-p1-research-team" ;;
  p2-arch-team-orchestrator)      SKILL_NAME="rtl-p2-arch-team" ;;
  p3-uarch-team-orchestrator)     SKILL_NAME="rtl-p3-uarch-team" ;;
  p4-implement-team-orchestrator) SKILL_NAME="rtl-p4-implement-team" ;;
  p5-verify-team-orchestrator)    SKILL_NAME="rtl-p5-verify-team" ;;
  spec-to-uarch-team-orchestrator) SKILL_NAME="rtl-spec-to-uarch-team" ;;
  *)
    printf '{"continue":true}'
    exit 0
    ;;
esac

# Always write/overwrite manifest to ensure phase/skill context is current.
if [ -n "$SKILL_NAME" ]; then
  sctx_write_manifest "$CWD" "$SKILL_NAME"
fi

printf '{"continue":true}'
