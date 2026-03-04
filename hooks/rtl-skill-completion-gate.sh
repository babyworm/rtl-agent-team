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

# Load flock utility for concurrent access protection
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
SKILL_STATE="$STATE_DIR/skill-active.json"

json_escape() {
  jsonu_escape "$1"
}

if teamu_should_skip_gate "$STATE_DIR"; then
  printf '{"continue":true}'
  exit 0
fi

# If no active skill state, allow exit
if [ ! -f "$SKILL_STATE" ]; then
  printf '{"continue":true}'
  exit 0
fi

# Check staleness (2 hours = 7200 seconds)
STARTED_AT=$(jsonu_get_file_path_string "$SKILL_STATE" "started_at")
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
SKILL_NAME=$(jsonu_get_file_path_string "$SKILL_STATE" "skill")
ITERATION=$(jsonu_get_file_path_num "$SKILL_STATE" "iteration")
MAX_ITER=$(jsonu_get_file_path_num "$SKILL_STATE" "max_iterations")
COMPLETED=$(jsonu_get_file_path_bool "$SKILL_STATE" "all_complete")
PENDING=$(jsonu_get_file_path_string "$SKILL_STATE" "pending")

# Default values
ITERATION=${ITERATION:-1}
MAX_ITER=${MAX_ITER:-5}

# If all complete, clean up and allow exit
if [ "$COMPLETED" = "true" ]; then
  rm -f "$SKILL_STATE"
  printf '{"continue":true}'
  exit 0
fi

LADDER_ENABLED=$(jsonu_get_file_path_bool "$SKILL_STATE" "use_escalation_ladder")
LADDER_ENABLED=${LADDER_ENABLED:-true}
DYNAMIC_PROMPT=$(jsonu_get_file_path_string "$SKILL_STATE" "dynamic_prompt")

# One-time migration: legacy states with ladder disabled are forced to ladder mode.
# Deferred to inside the lock block below to avoid racing with the iteration update.

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

# Lock state file for atomic iteration increment + strategy update + migration
if acquire_lock "$SKILL_STATE"; then
  # Build sed script file for single atomic read→transform→mv
  _SED_SCRIPT=$(mktemp "${TMPDIR:-/tmp}/skill-gate-sed.XXXXXX" 2>/dev/null || echo "$SKILL_STATE.sed")
  printf 's/"iteration"[[:space:]]*:[[:space:]]*[0-9]*/"iteration": %s/\n' "$NEXT_ITER" > "$_SED_SCRIPT"
  if grep -q '"strategy"' "$SKILL_STATE" 2>/dev/null; then
    printf 's/"strategy"[[:space:]]*:[[:space:]]*"[^"]*"/"strategy": "%s"/\n' "$STAGE" >> "$_SED_SCRIPT"
  fi
  if [ "$LADDER_ENABLED" != "true" ] && grep -q '"use_escalation_ladder"' "$SKILL_STATE" 2>/dev/null; then
    printf 's/"use_escalation_ladder"[[:space:]]*:[[:space:]]*false/"use_escalation_ladder": true/\n' >> "$_SED_SCRIPT"
  fi
  sed -f "$_SED_SCRIPT" "$SKILL_STATE" > "$SKILL_STATE.tmp" 2>/dev/null && mv "$SKILL_STATE.tmp" "$SKILL_STATE"
  rm -f "$_SED_SCRIPT" 2>/dev/null
  release_lock "$SKILL_STATE"
fi

printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(json_escape "$STAGE_MSG")"
