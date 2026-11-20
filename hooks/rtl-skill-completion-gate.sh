#!/bin/sh
# RTL Skill Completion Gate: keeps Claude working while an active RTL skill has pending
# completion criteria. When a pipeline skill's orchestrator waits for the user's decision,
# it hands over to the user instead.
#
# State file: .rat/state/skill-active.json
# Contains: skill name, iteration count, pending criteria, all_complete flag
#
# Missing criteria produce one bounded reminder. Legacy iteration fields do not
# schedule reviews. Infeasibility and user decisions yield immediately.
# Activity refreshes the two-hour abandonment bound.
#
# Every block goes through hooks/lib/stop-budget-util.sh: after RAT_STOP_BLOCK_LIMIT blocks
# without progress (no change in the pending criteria) in one continuation chain, the gate
# lets Claude stop and shows the user a notice. From the chain's Stop STOPU_CHAIN_CAP + 1 on,
# whichever hooks blocked the earlier Stops, the gate shows the notice instead of blocking.
# Completion reminders never schedule another review round.

INPUT=$(cat)

# Load flock utility for concurrent access protection
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/stop-budget-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
. "$SCRIPT_DIR/lib/compliance-gate-util.sh"
. "$SCRIPT_DIR/lib/posix-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_root_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_DIR="$RAT_DIR/state"
SKILL_STATE="$STATE_DIR/skill-active.json"

if teamu_should_skip_gate "$STATE_DIR" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" skill-completion)
if stopu_background_agent_pending "$INPUT"; then
  [ ! -f "$SKILL_STATE" ] || touch "$SKILL_STATE"
  emit_post_continue
fi  # paused for a background agent; its completion wakes the session

# If no active skill state, allow exit
if [ ! -f "$SKILL_STATE" ]; then
  stopu_clear skill-completion "$STATE_DIR"
  emit_post_continue
fi

# Check staleness (2 hours = 7200 seconds)
STARTED_AT=$(jsonu_get_file_path_string "$SKILL_STATE" "started_at")
if [ -n "$STARTED_AT" ]; then
  # Convert to epoch — try GNU date -d, then BSD date -jf, then skip
  START_EPOCH=$(date -d "$STARTED_AT" +%s 2>/dev/null || TZ=UTC date -jf "%Y-%m-%dT%H:%M:%S" "${STARTED_AT%Z}" +%s 2>/dev/null || echo "")
  NOW_EPOCH=$(date +%s 2>/dev/null)
  if [ -n "$START_EPOCH" ] && [ -n "$NOW_EPOCH" ]; then
    ACTIVE_MTIME=$(get_mtime_epoch "$SKILL_STATE")
    [ -z "$ACTIVE_MTIME" ] || [ "$ACTIVE_MTIME" -le "$START_EPOCH" ] || START_EPOCH=$ACTIVE_MTIME
    AGE=$(( NOW_EPOCH - START_EPOCH ))
    if [ "$AGE" -gt 7200 ]; then
      # Stale state, clean up and allow exit
      rm -f "$SKILL_STATE"
      stopu_clear skill-completion "$STATE_DIR"
      MSG="[RAT] An abandoned skill loop was cleared after 7200s without activity. Its pending work has not been marked complete."
      stopu_gate skill-completion "$STATE_DIR" "$STOP_CHAIN" stale-loop "$MSG" "$MSG" 0
    fi
  fi
fi

jsonu_cache_file "$SKILL_STATE"

# Read state fields that are stable (not mutated by this hook)
SKILL_NAME=$(jsonu_get_file_path_string "$SKILL_STATE" "skill")
COMPLETED=$(jsonu_get_file_path_bool "$SKILL_STATE" "all_complete")
PENDING=$(jsonu_get_file_path_string "$SKILL_STATE" "pending")

# Compliance-pass auto-resolution: delegated to compliance-gate-util.sh
compliance_preprocess "$SKILL_STATE" "$STATE_DIR" "$PENDING"
PENDING="$_CGU_PENDING"
jsonu_cache_file "$SKILL_STATE"

# Re-check completion after compliance preprocessing may have cleared last criterion
if [ -z "$PENDING" ] || [ "$PENDING" = "null" ]; then
  COMPLETED="true"
fi

# If all complete, clean up and allow exit
if [ "$COMPLETED" = "true" ]; then
  rm -f "$SKILL_STATE"
  stopu_clear skill-completion "$STATE_DIR"
  emit_post_continue
fi

# Progress means the pending criteria changed; the ladder counts attempts across turns.
SKILL_PROGRESS="$SKILL_NAME|$PENDING"
SKILL_NOTICE="[RTL Skill Completion Loop] ${SKILL_NAME} still has pending criteria: ${PENDING}. The skill completion gate is not asking Claude to continue in this turn. Say continue to resume."
# On an upstream challenge the user's decision is about the upstream requirement, not about continuing.
UPSTREAM_NOTICE="[Upstream Challenge] ${SKILL_NAME}: the compliance checker found an iron requirement that cannot be met. The skill completion gate is not asking Claude to continue in this turn. Review the Upstream Challenge Report (or ask Claude for it) and decide whether to amend the upstream requirement. Remaining criteria: ${PENDING}."
GATE_NOTICE=$SKILL_NOTICE
if [ "$(jsonu_get_file_path_string "$SKILL_STATE" "strategy")" = "upstream_challenge" ]; then
  GATE_NOTICE=$UPSTREAM_NOTICE
fi

# The refC wrapper delegates with Skill(), which can leave its child as the active skill.
PIPELINE_NAME=$SKILL_NAME
REFC_STATE="$STATE_DIR/rat-refc-to-p5-state.json"
if [ -f "$REFC_STATE" ] && [ "$SKILL_NAME" = "$(jsonu_get_file_path_string "$REFC_STATE" current_skill)" ]; then
  PIPELINE_NAME=rat-refc-to-p5
fi
case "$PIPELINE_NAME" in
  rat-auto-design|rat-p1p3-spec-uarch|rat-p4p5-impl-verify|rat-refc-to-p5)
    if stopu_pipeline_waits "$STATE_DIR/${PIPELINE_NAME}-state.json"; then
      PIPELINE_NOTICE="Info> ${PIPELINE_NAME} is waiting for your decision."
      stopu_gate skill-completion "$STATE_DIR" "$STOP_CHAIN" "$SKILL_PROGRESS" "$PIPELINE_NOTICE" "$PIPELINE_NOTICE" 0
    fi
    ;;
esac

if stopu_pipeline_waits "$STATE_DIR/rat-auto-design-state.json"; then
  stopu_gate skill-completion "$STATE_DIR" "$STOP_CHAIN" "$SKILL_PROGRESS" "$GATE_NOTICE" "$GATE_NOTICE" 0
fi
if [ "$(jsonu_get_file_path_string "$SKILL_STATE" strategy)" = upstream_challenge ]; then
  stopu_gate skill-completion "$STATE_DIR" "$STOP_CHAIN" "$SKILL_PROGRESS" "$UPSTREAM_NOTICE" "$UPSTREAM_NOTICE" 0
fi
MSG="[RTL Skill Completion] ${SKILL_NAME}: remaining criteria ${PENDING}. Produce missing artifacts or repair the concrete failed check, then rerun affected checks. Do not repeat successful reviews or analysis to raise confidence."
stopu_gate skill-completion "$STATE_DIR" "$STOP_CHAIN" "$SKILL_PROGRESS" "$MSG" "$GATE_NOTICE" 1
