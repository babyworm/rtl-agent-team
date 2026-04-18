#!/bin/sh
# Stop Gate: block session exit while rat-auto-design is running.
# Supports escalation ladder:
#   primary attempts (<=N) -> fallback strategy (N+1..2N) -> last chance (2N+1) -> user escalation.

INPUT=$(cat)

# Load flock utility for concurrent access protection
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }

STATE_FILE="$RAT_DIR/state/rat-auto-design-state.json"

# Legacy migration: rename old state file from pre-0.6.10 naming convention
LEGACY_STATE_FILE="$RAT_DIR/state/rtl-autopilot-state.json"
if [ ! -f "$STATE_FILE" ] && [ -f "$LEGACY_STATE_FILE" ]; then
  mv "$LEGACY_STATE_FILE" "$STATE_FILE"
fi

if teamu_should_skip_gate "$RAT_DIR/state"; then
  emit_post_continue
fi

# Ultraloop auto-continue: if ultraloop is active and within its time window, keep going
ULTRALOOP_STATE="$RAT_DIR/state/ultraloop-state.json"
if [ -f "$ULTRALOOP_STATE" ]; then
  . "$SCRIPT_DIR/lib/posix-util.sh"
  UL_MODE=$(jsonu_get_file_path_string "$ULTRALOOP_STATE" "mode")
  if [ "$UL_MODE" = "ultraloop" ]; then
    UL_TIMESTAMP=$(jsonu_get_file_path_num "$ULTRALOOP_STATE" "last_cycle_timestamp")
    UL_MINUTES=$(jsonu_get_file_path_num "$ULTRALOOP_STATE" "auto_continue_minutes")
    [ -z "$UL_MINUTES" ] && UL_MINUTES=30
    UL_THRESHOLD=$((UL_MINUTES * 60))
    UL_ELAPSED=$(posix_elapsed_seconds "$UL_TIMESTAMP")
    if [ "$UL_ELAPSED" -lt "$UL_THRESHOLD" ]; then
      MSG="[Ultraloop] auto-continue: ${UL_ELAPSED}s elapsed (threshold=${UL_THRESHOLD}s). Continuing autonomous loop."
      emit_stop_block "$MSG"
    fi
  fi
fi

# PPA-Opt loop auto-continue: if ppa-loop is active and within its time window, keep going
PPA_LOOP_STATE="$RAT_DIR/state/ppa-loop-state.json"
if [ -f "$PPA_LOOP_STATE" ]; then
  . "$SCRIPT_DIR/lib/posix-util.sh"
  PPA_MODE=$(jsonu_get_file_path_string "$PPA_LOOP_STATE" "mode")
  if [ "$PPA_MODE" = "ppa-loop" ]; then
    PPA_TIMESTAMP=$(jsonu_get_file_path_num "$PPA_LOOP_STATE" "last_cycle_timestamp")
    PPA_MINUTES=$(jsonu_get_file_path_num "$PPA_LOOP_STATE" "auto_continue_minutes")
    [ -z "$PPA_MINUTES" ] && PPA_MINUTES=30
    PPA_THRESHOLD=$((PPA_MINUTES * 60))
    PPA_ELAPSED=$(posix_elapsed_seconds "$PPA_TIMESTAMP")
    if [ "$PPA_ELAPSED" -lt "$PPA_THRESHOLD" ]; then
      MSG="[PPA-Opt loop] auto-continue: ${PPA_ELAPSED}s elapsed (threshold=${PPA_THRESHOLD}s). Continuing PPA optimization loop."
      emit_stop_block "$MSG"
    fi
  fi
fi

if [ ! -f "$STATE_FILE" ]; then
  emit_post_continue
fi

STATUS=$(jsonu_get_file_path_string "$STATE_FILE" "status")
if [ "$STATUS" = "completed" ]; then
  emit_post_continue
fi

UPPER_SPEC_BLOCKING=$(jsonu_get_file_path_bool "$STATE_FILE" "upper_spec_blocking")
if [ "$UPPER_SPEC_BLOCKING" = "true" ]; then
  MSG="[RAT Auto-Design STOP] Upper-spec violation is unresolved. Resolve violation or obtain user approval before proceeding."
  emit_stop_block "$MSG"
fi

ACTIVE_GATE_ID=$(jsonu_get_file_path_string "$STATE_FILE" "orchestration_control.active_gate_id")
[ -z "$ACTIVE_GATE_ID" ] && ACTIVE_GATE_ID="phase-gate"

RETRY_LIMIT=$(jsonu_get_file_path_num "$STATE_FILE" "orchestration_control.active_gate_retry_limit")
[ -z "$RETRY_LIMIT" ] && RETRY_LIMIT=$(jsonu_get_file_path_num "$STATE_FILE" "orchestration_control.default_retry_limit")
[ -z "$RETRY_LIMIT" ] && RETRY_LIMIT=2

PRIMARY_ATTEMPTS=$(jsonu_get_file_path_num "$STATE_FILE" "orchestration_control.active_gate_primary_attempts")
[ -z "$PRIMARY_ATTEMPTS" ] && PRIMARY_ATTEMPTS=0
FALLBACK_ATTEMPTS=$(jsonu_get_file_path_num "$STATE_FILE" "orchestration_control.active_gate_fallback_attempts")
[ -z "$FALLBACK_ATTEMPTS" ] && FALLBACK_ATTEMPTS=0
LAST_CHANCE_ATTEMPTS=$(jsonu_get_file_path_num "$STATE_FILE" "orchestration_control.active_gate_last_chance_attempts")
[ -z "$LAST_CHANCE_ATTEMPTS" ] && LAST_CHANCE_ATTEMPTS=0

NEEDS_USER_DECISION=$(jsonu_get_file_path_bool "$STATE_FILE" "orchestration_control.needs_user_decision")
[ -z "$NEEDS_USER_DECISION" ] && NEEDS_USER_DECISION=false
DYNAMIC_PROMPT_TEXT=$(jsonu_get_file_path_string "$STATE_FILE" "orchestration_control.dynamic_prompt_text")
STRATEGY=$(jsonu_get_file_path_string "$STATE_FILE" "orchestration_control.active_gate_strategy")

TOTAL_PHASE_ATTEMPTS=$((PRIMARY_ATTEMPTS + FALLBACK_ATTEMPTS))
FALLBACK_START=$((RETRY_LIMIT + 1))
FALLBACK_END=$((RETRY_LIMIT * 2))

if [ "$TOTAL_PHASE_ATTEMPTS" -le "$RETRY_LIMIT" ]; then
  [ -z "$STRATEGY" ] && STRATEGY="primary"
  MSG="[RAT Auto-Design Loop ${ACTIVE_GATE_ID}] primary strategy (${TOTAL_PHASE_ATTEMPTS}/${RETRY_LIMIT}). Continue agent loop and satisfy the gate conditions."
elif [ "$TOTAL_PHASE_ATTEMPTS" -le "$FALLBACK_END" ]; then
  [ -z "$STRATEGY" ] && STRATEGY="fallback"
  MSG="[RAT Auto-Design Loop ${ACTIVE_GATE_ID}] fallback strategy (${TOTAL_PHASE_ATTEMPTS}/${FALLBACK_START}-${FALLBACK_END}). Split failure scope and switch agent composition."
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    MSG="${MSG} Dynamic prompt: ${DYNAMIC_PROMPT_TEXT}"
  fi
elif [ "$LAST_CHANCE_ATTEMPTS" -lt 1 ]; then
  [ -z "$STRATEGY" ] && STRATEGY="last_chance"
  MSG="[RAT Auto-Design Loop ${ACTIVE_GATE_ID}] reached 2x retry budget. Execute one last-chance alternative strategy now."
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    MSG="${MSG} Dynamic prompt: ${DYNAMIC_PROMPT_TEXT}"
  fi
else
  NEEDS_USER_DECISION=true
  [ -z "$STRATEGY" ] && STRATEGY="user_escalated"
  MSG="[RAT Auto-Design Loop ${ACTIVE_GATE_ID}] last-chance attempt exhausted. Ask user for direction before further retries."
fi

if [ "$NEEDS_USER_DECISION" = "true" ]; then
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    MSG="${MSG} Suggested context: ${DYNAMIC_PROMPT_TEXT}"
  fi
fi

MSG="${MSG} (strategy=${STRATEGY}, primary=${PRIMARY_ATTEMPTS}, fallback=${FALLBACK_ATTEMPTS}, last_chance=${LAST_CHANCE_ATTEMPTS})"
emit_stop_block "$MSG"
