#!/bin/sh
# Stop Gate: block session exit while rtl-autopilot is running.
# Supports escalation ladder:
#   primary attempts (<=N) -> fallback strategy (N+1..2N) -> last chance (2N+1) -> user escalation.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_FILE="$CWD/.rtl-agent-team/state/rtl-autopilot-state.json"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

get_string() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$STATE_FILE" | head -n 1
}

get_bool() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p" "$STATE_FILE" | head -n 1
}

get_num() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p" "$STATE_FILE" | head -n 1
}

if [ ! -f "$STATE_FILE" ]; then
  printf '{"continue":true}'
  exit 0
fi

STATUS=$(get_string "status")
if [ "$STATUS" = "completed" ]; then
  printf '{"continue":true}'
  exit 0
fi

UPPER_SPEC_BLOCKING=$(get_bool "upper_spec_blocking")
if [ "$UPPER_SPEC_BLOCKING" = "true" ]; then
  MSG="[RTL Autopilot STOP] Upper-spec violation is unresolved. Resolve violation or obtain user approval before proceeding."
  printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(json_escape "$MSG")"
  exit 0
fi

ACTIVE_GATE_ID=$(get_string "active_gate_id")
[ -z "$ACTIVE_GATE_ID" ] && ACTIVE_GATE_ID="phase-gate"

RETRY_LIMIT=$(get_num "active_gate_retry_limit")
[ -z "$RETRY_LIMIT" ] && RETRY_LIMIT=$(get_num "default_retry_limit")
[ -z "$RETRY_LIMIT" ] && RETRY_LIMIT=2

PRIMARY_ATTEMPTS=$(get_num "active_gate_primary_attempts")
[ -z "$PRIMARY_ATTEMPTS" ] && PRIMARY_ATTEMPTS=0
FALLBACK_ATTEMPTS=$(get_num "active_gate_fallback_attempts")
[ -z "$FALLBACK_ATTEMPTS" ] && FALLBACK_ATTEMPTS=0
LAST_CHANCE_ATTEMPTS=$(get_num "active_gate_last_chance_attempts")
[ -z "$LAST_CHANCE_ATTEMPTS" ] && LAST_CHANCE_ATTEMPTS=0

NEEDS_USER_DECISION=$(get_bool "needs_user_decision")
[ -z "$NEEDS_USER_DECISION" ] && NEEDS_USER_DECISION=false
DYNAMIC_PROMPT_TEXT=$(get_string "dynamic_prompt_text")
STRATEGY=$(get_string "active_gate_strategy")

TOTAL_PHASE_ATTEMPTS=$((PRIMARY_ATTEMPTS + FALLBACK_ATTEMPTS))
FALLBACK_START=$((RETRY_LIMIT + 1))
FALLBACK_END=$((RETRY_LIMIT * 2))

if [ "$TOTAL_PHASE_ATTEMPTS" -le "$RETRY_LIMIT" ]; then
  [ -z "$STRATEGY" ] && STRATEGY="primary"
  MSG="[RTL Autopilot Loop ${ACTIVE_GATE_ID}] primary strategy (${TOTAL_PHASE_ATTEMPTS}/${RETRY_LIMIT}). Continue agent loop and satisfy the gate conditions."
elif [ "$TOTAL_PHASE_ATTEMPTS" -le "$FALLBACK_END" ]; then
  [ -z "$STRATEGY" ] && STRATEGY="fallback"
  MSG="[RTL Autopilot Loop ${ACTIVE_GATE_ID}] fallback strategy (${TOTAL_PHASE_ATTEMPTS}/${FALLBACK_START}-${FALLBACK_END}). Split failure scope and switch agent composition."
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    MSG="${MSG} Dynamic prompt: ${DYNAMIC_PROMPT_TEXT}"
  fi
elif [ "$LAST_CHANCE_ATTEMPTS" -lt 1 ]; then
  [ -z "$STRATEGY" ] && STRATEGY="last_chance"
  MSG="[RTL Autopilot Loop ${ACTIVE_GATE_ID}] reached 2x retry budget. Execute one last-chance alternative strategy now."
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    MSG="${MSG} Dynamic prompt: ${DYNAMIC_PROMPT_TEXT}"
  fi
else
  NEEDS_USER_DECISION=true
  [ -z "$STRATEGY" ] && STRATEGY="user_escalated"
  MSG="[RTL Autopilot Loop ${ACTIVE_GATE_ID}] last-chance attempt exhausted. Ask user for direction before further retries."
fi

if [ "$NEEDS_USER_DECISION" = "true" ]; then
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    MSG="${MSG} Suggested context: ${DYNAMIC_PROMPT_TEXT}"
  fi
fi

MSG="${MSG} (strategy=${STRATEGY}, primary=${PRIMARY_ATTEMPTS}, fallback=${FALLBACK_ATTEMPTS}, last_chance=${LAST_CHANCE_ATTEMPTS})"
printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(json_escape "$MSG")"
