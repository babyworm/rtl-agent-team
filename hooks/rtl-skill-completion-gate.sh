#!/bin/sh
# RTL Skill Completion Gate: blocks session exit if an RTL skill is active without completion.
#
# State file: .rtl-agent-team/state/skill-active.json
# Contains: skill name, iteration count, pending criteria, all_complete flag
#
# If skill is active and not all_complete, session exit is BLOCKED and iteration incremented.
# max_iterations is treated as primary retry budget (N): N -> 2N -> last-chance -> user escalation.
# Staleness check: state older than 2 hours is ignored (prevents blocking new sessions).

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
SKILL_STATE="$STATE_DIR/skill-active.json"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

# If no active skill state, allow exit
if [ ! -f "$SKILL_STATE" ]; then
  printf '{"continue":true}'
  exit 0
fi

# Check staleness (2 hours = 7200 seconds)
STARTED_AT=$(sed -n 's/.*"started_at"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SKILL_STATE")
if [ -n "$STARTED_AT" ]; then
  # Convert to epoch — try GNU date -d, then BSD date -jf, then skip
  START_EPOCH=$(date -d "$STARTED_AT" +%s 2>/dev/null || date -jf "%Y-%m-%dT%H:%M:%SZ" "$STARTED_AT" +%s 2>/dev/null || echo "")
  NOW_EPOCH=$(date +%s 2>/dev/null)
  if [ -n "$START_EPOCH" ] && [ -n "$NOW_EPOCH" ]; then
    AGE=$(( NOW_EPOCH - START_EPOCH ))
    if [ "$AGE" -gt 7200 ]; then
      # Stale state, clean up and allow exit
      rm -f "$SKILL_STATE"
      printf '{"continue":true}'
      exit 0
    fi
  fi
fi

# Read state fields
SKILL_NAME=$(sed -n 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SKILL_STATE")
ITERATION=$(sed -n 's/.*"iteration"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$SKILL_STATE")
MAX_ITER=$(sed -n 's/.*"max_iterations"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$SKILL_STATE")
COMPLETED=$(sed -n 's/.*"all_complete"[[:space:]]*:[[:space:]]*\([a-z]*\).*/\1/p' "$SKILL_STATE")
PENDING=$(sed -n 's/.*"pending"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SKILL_STATE")

# Default values
ITERATION=${ITERATION:-1}
MAX_ITER=${MAX_ITER:-5}

# If all complete, clean up and allow exit
if [ "$COMPLETED" = "true" ]; then
  rm -f "$SKILL_STATE"
  printf '{"continue":true}'
  exit 0
fi

LADDER_ENABLED=$(sed -n 's/.*"use_escalation_ladder"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' "$SKILL_STATE")
LADDER_ENABLED=${LADDER_ENABLED:-true}
DYNAMIC_PROMPT=$(sed -n 's/.*"dynamic_prompt"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SKILL_STATE")

# One-time migration: legacy states with ladder disabled are forced to ladder mode.
if [ "$LADDER_ENABLED" != "true" ] && grep -q '"use_escalation_ladder"' "$SKILL_STATE" 2>/dev/null; then
  sed 's/"use_escalation_ladder"[[:space:]]*:[[:space:]]*false/"use_escalation_ladder": true/' "$SKILL_STATE" > "$SKILL_STATE.tmp" 2>/dev/null && mv "$SKILL_STATE.tmp" "$SKILL_STATE"
fi

TWO_X_LIMIT=$((MAX_ITER * 2))
LAST_CHANCE_INDEX=$((TWO_X_LIMIT + 1))
NEXT_ITER=$((ITERATION + 1))

if [ "$ITERATION" -le "$MAX_ITER" ]; then
  STAGE="primary"
  STAGE_MSG="[RTL Skill Completion Loop - ${ITERATION}/${MAX_ITER}] ${SKILL_NAME} primary 전략 반복 중. 남은 조건: ${PENDING}."
elif [ "$ITERATION" -le "$TWO_X_LIMIT" ]; then
  STAGE="fallback"
  STAGE_MSG="[RTL Skill Completion Loop - ${ITERATION}/${TWO_X_LIMIT}] ${SKILL_NAME} fallback 전략 반복 중. 실패 영역 분해 + 에이전트 조합 전환을 적용하세요. 남은 조건: ${PENDING}."
  if [ -n "$DYNAMIC_PROMPT" ]; then
    STAGE_MSG="${STAGE_MSG} Dynamic prompt: ${DYNAMIC_PROMPT}"
  fi
elif [ "$ITERATION" -eq "$LAST_CHANCE_INDEX" ]; then
  STAGE="last_chance"
  STAGE_MSG="[RTL Skill Completion Loop - last_chance] ${SKILL_NAME} 2x 반복 초과. 대안 전략 1회 자동 실행 단계입니다. 남은 조건: ${PENDING}."
  if [ -n "$DYNAMIC_PROMPT" ]; then
    STAGE_MSG="${STAGE_MSG} Dynamic prompt: ${DYNAMIC_PROMPT}"
  fi
else
  STAGE="user_escalated"
  STAGE_MSG="[RTL Skill Completion Loop - escalation] ${SKILL_NAME} last_chance 실패. 사용자 결정이 필요합니다. 남은 조건: ${PENDING}."
  if [ -n "$DYNAMIC_PROMPT" ]; then
    STAGE_MSG="${STAGE_MSG} Suggested context: ${DYNAMIC_PROMPT}"
  fi
fi

sed "s/\"iteration\"[[:space:]]*:[[:space:]]*[0-9]*/\"iteration\": $NEXT_ITER/" "$SKILL_STATE" > "$SKILL_STATE.tmp" 2>/dev/null && mv "$SKILL_STATE.tmp" "$SKILL_STATE"

# Best-effort mark of current stage for external readers.
if grep -q '"strategy"' "$SKILL_STATE" 2>/dev/null; then
  sed "s/\"strategy\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"strategy\": \"$STAGE\"/" "$SKILL_STATE" > "$SKILL_STATE.tmp" 2>/dev/null && mv "$SKILL_STATE.tmp" "$SKILL_STATE"
fi

printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(json_escape "$STAGE_MSG")"
