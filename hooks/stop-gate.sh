#!/bin/sh
# Stop Gate: block session exit while rat-auto-design is running.
# Supports escalation ladder:
#   primary attempts (<=N) -> fallback strategy (N+1..2N) -> last chance (2N+1) -> user escalation.

INPUT=$(cat)

# Load flock utility for concurrent access protection
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_FILE="$CWD/.rtl-agent-team/state/rat-auto-design-state.json"

json_escape() {
  jsonu_escape "$1"
}

get_path_string() {
  jsonu_get_file_path_string "$STATE_FILE" "$1"
}

get_path_bool() {
  jsonu_get_file_path_bool "$STATE_FILE" "$1"
}

get_path_num() {
  jsonu_get_file_path_num "$STATE_FILE" "$1"
}

if teamu_should_skip_gate "$CWD/.rtl-agent-team/state"; then
  printf '{"continue":true}'
  exit 0
fi

if [ ! -f "$STATE_FILE" ]; then
  printf '{"continue":true}'
  exit 0
fi

STATUS=$(get_path_string "status")
if [ "$STATUS" = "completed" ]; then
  printf '{"continue":true}'
  exit 0
fi

UPPER_SPEC_BLOCKING=$(get_path_bool "upper_spec_blocking")
if [ "$UPPER_SPEC_BLOCKING" = "true" ]; then
  MSG="[RAT Auto-Design STOP] Upper-spec violation is unresolved. Resolve violation or obtain user approval before proceeding."
  printf '{"continue":false,"decision":"block","reason":"%s"}' "$(json_escape "$MSG")"
  exit 0
fi

ACTIVE_GATE_ID=$(get_path_string "orchestration_control.active_gate_id")
[ -z "$ACTIVE_GATE_ID" ] && ACTIVE_GATE_ID="phase-gate"

RETRY_LIMIT=$(get_path_num "orchestration_control.active_gate_retry_limit")
[ -z "$RETRY_LIMIT" ] && RETRY_LIMIT=$(get_path_num "orchestration_control.default_retry_limit")
[ -z "$RETRY_LIMIT" ] && RETRY_LIMIT=2

PRIMARY_ATTEMPTS=$(get_path_num "orchestration_control.active_gate_primary_attempts")
[ -z "$PRIMARY_ATTEMPTS" ] && PRIMARY_ATTEMPTS=0
FALLBACK_ATTEMPTS=$(get_path_num "orchestration_control.active_gate_fallback_attempts")
[ -z "$FALLBACK_ATTEMPTS" ] && FALLBACK_ATTEMPTS=0
LAST_CHANCE_ATTEMPTS=$(get_path_num "orchestration_control.active_gate_last_chance_attempts")
[ -z "$LAST_CHANCE_ATTEMPTS" ] && LAST_CHANCE_ATTEMPTS=0

NEEDS_USER_DECISION=$(get_path_bool "orchestration_control.needs_user_decision")
[ -z "$NEEDS_USER_DECISION" ] && NEEDS_USER_DECISION=false
DYNAMIC_PROMPT_TEXT=$(get_path_string "orchestration_control.dynamic_prompt_text")
STRATEGY=$(get_path_string "orchestration_control.active_gate_strategy")

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
printf '{"continue":false,"decision":"block","reason":"%s"}' "$(json_escape "$MSG")"
