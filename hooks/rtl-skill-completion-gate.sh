#!/bin/sh
# RTL Skill Completion Gate: blocks session exit if an RTL skill is active without completion.
#
# State file: .rtl-agent-team/state/skill-active.json
# Contains: skill name, iteration count, pending criteria, all_complete flag
#
# If skill is active and not all_complete, session exit is BLOCKED and iteration incremented.
# Max iterations prevents infinite loops (default 5).
# Staleness check: state older than 2 hours is ignored (prevents blocking new sessions).

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
SKILL_STATE="$STATE_DIR/skill-active.json"

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

# Check max iterations
if [ "$ITERATION" -ge "$MAX_ITER" ]; then
  rm -f "$SKILL_STATE"
  printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[RTL Skill Loop] %s 최대 반복(%s회) 도달. 완료되지 않았지만 루프를 종료합니다. 수동 확인이 필요합니다."}}' "$SKILL_NAME" "$MAX_ITER"
  exit 0
fi

# Skill not complete — BLOCK exit and increment iteration
NEW_ITER=$((ITERATION + 1))
sed "s/\"iteration\"[[:space:]]*:[[:space:]]*[0-9]*/\"iteration\": $NEW_ITER/" "$SKILL_STATE" > "$SKILL_STATE.tmp" 2>/dev/null && mv "$SKILL_STATE.tmp" "$SKILL_STATE"

printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[RTL Skill Completion Loop - %s/%s] %s 스킬이 아직 완료되지 않았습니다. 남은 조건: %s. 작업을 계속 진행하세요. 모든 조건 충족 시 .rtl-agent-team/state/skill-active.json 의 all_complete 를 true 로 설정하세요."}}' "$NEW_ITER" "$MAX_ITER" "$SKILL_NAME" "$PENDING"
