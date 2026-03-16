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
. "$SCRIPT_DIR/lib/compliance-gate-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
SKILL_STATE="$STATE_DIR/skill-active.json"

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

# Read state fields that are stable (not mutated by this hook)
SKILL_NAME=$(jsonu_get_file_path_string "$SKILL_STATE" "skill")
COMPLETED=$(jsonu_get_file_path_bool "$SKILL_STATE" "all_complete")
PENDING=$(jsonu_get_file_path_string "$SKILL_STATE" "pending")

# Compliance-pass auto-resolution: delegated to compliance-gate-util.sh
compliance_preprocess "$SKILL_STATE" "$STATE_DIR" "$PENDING"
PENDING="$_CGU_PENDING"

# If all complete, clean up and allow exit
if [ "$COMPLETED" = "true" ]; then
  rm -f "$SKILL_STATE"
  printf '{"continue":true}'
  exit 0
fi

DYNAMIC_PROMPT=$(jsonu_get_file_path_string "$SKILL_STATE" "dynamic_prompt")

# Lock state file for atomic read → compute → write of mutable fields
STAGE=""
ITERATION=""
NEXT_ITER=""
if acquire_lock "$SKILL_STATE"; then
  # Read mutable fields inside lock to prevent TOCTOU races
  ITERATION=$(jsonu_get_file_path_num "$SKILL_STATE" "iteration")
  MAX_ITER=$(jsonu_get_file_path_num "$SKILL_STATE" "max_iterations")
  LADDER_ENABLED=$(jsonu_get_file_path_bool "$SKILL_STATE" "use_escalation_ladder")

  # Default values
  ITERATION=${ITERATION:-1}
  MAX_ITER=${MAX_ITER:-5}
  LADDER_ENABLED=${LADDER_ENABLED:-true}

  # Authority-differentiated budgets: if max_primary/max_fallback are set
  # (written by compliance-pass pre-processing), use them instead of default N/2N
  _CUSTOM_PRIMARY=$(jsonu_get_file_path_num "$SKILL_STATE" "max_primary")
  _CUSTOM_FALLBACK=$(jsonu_get_file_path_num "$SKILL_STATE" "max_fallback")
  if [ -n "$_CUSTOM_PRIMARY" ] && [ "$_CUSTOM_PRIMARY" != "null" ]; then
    PRIMARY_LIMIT=$_CUSTOM_PRIMARY
    FALLBACK_LIMIT=$((_CUSTOM_PRIMARY + _CUSTOM_FALLBACK))
  else
    PRIMARY_LIMIT=$MAX_ITER
    FALLBACK_LIMIT=$((MAX_ITER * 2))
  fi
  LAST_CHANCE_INDEX=$((FALLBACK_LIMIT + 1))
  NEXT_ITER=$((ITERATION + 1))

  # Determine escalation stage using authority-aware limits
  if [ "$ITERATION" -le "$PRIMARY_LIMIT" ]; then
    STAGE="primary"
  elif [ "$ITERATION" -le "$FALLBACK_LIMIT" ]; then
    STAGE="fallback"
  elif [ "$ITERATION" -eq "$LAST_CHANCE_INDEX" ]; then
    STAGE="last_chance"
  else
    STAGE="user_escalated"
  fi

  # Preserve TWO_X_LIMIT for stage message (backward compat)
  TWO_X_LIMIT=$FALLBACK_LIMIT

  # Build sed script file for single atomic read→transform→mv
  _SED_SCRIPT=$(mktemp "${TMPDIR:-/tmp}/skill-gate-sed.XXXXXX" 2>/dev/null || echo "$SKILL_STATE.sed")
  printf 's/"iteration"[[:space:]]*:[[:space:]]*[0-9]*/"iteration": %s/\n' "$NEXT_ITER" > "$_SED_SCRIPT"
  # Preserve upstream_challenge strategy if set by compliance pre-processing
  _CURRENT_STRATEGY=$(jsonu_get_file_path_string "$SKILL_STATE" "strategy")
  if [ "$_CURRENT_STRATEGY" = "upstream_challenge" ]; then
    : # Do not overwrite upstream_challenge with ladder stage
  elif grep -q '"strategy"' "$SKILL_STATE" 2>/dev/null; then
    printf 's/"strategy"[[:space:]]*:[[:space:]]*"[^"]*"/"strategy": "%s"/\n' "$STAGE" >> "$_SED_SCRIPT"
  fi
  # One-time migration: legacy states with ladder disabled are forced to ladder mode.
  if [ "$LADDER_ENABLED" != "true" ] && grep -q '"use_escalation_ladder"' "$SKILL_STATE" 2>/dev/null; then
    printf 's/"use_escalation_ladder"[[:space:]]*:[[:space:]]*false/"use_escalation_ladder": true/\n' >> "$_SED_SCRIPT"
  fi
  sed -f "$_SED_SCRIPT" "$SKILL_STATE" > "$SKILL_STATE.tmp" 2>/dev/null \
    && mv "$SKILL_STATE.tmp" "$SKILL_STATE" \
    || rm -f "$SKILL_STATE.tmp" 2>/dev/null
  rm -f "$_SED_SCRIPT" 2>/dev/null
  release_lock "$SKILL_STATE"
fi

# Generate stage message outside lock (read-only, uses values determined above)
MAX_ITER=${MAX_ITER:-5}
TWO_X_LIMIT=${FALLBACK_LIMIT:-$((MAX_ITER * 2))}
case "$STAGE" in
  primary)
    _MSG_PRIMARY=${PRIMARY_LIMIT:-$MAX_ITER}
    STAGE_MSG="[RTL Skill Completion Loop - ${ITERATION}/${_MSG_PRIMARY}] ${SKILL_NAME} primary strategy iteration. Remaining criteria: ${PENDING}."
    ;;
  fallback)
    STAGE_MSG="[RTL Skill Completion Loop - ${ITERATION}/${TWO_X_LIMIT}] ${SKILL_NAME} fallback strategy iteration. Apply failure area decomposition + agent combination switching. Remaining criteria: ${PENDING}."
    if [ -n "$DYNAMIC_PROMPT" ]; then
      STAGE_MSG="${STAGE_MSG} Dynamic prompt: ${DYNAMIC_PROMPT}"
    fi
    ;;
  last_chance)
    STAGE_MSG="[RTL Skill Completion Loop - last_chance] ${SKILL_NAME} exceeded 2x iterations. One automatic alternative strategy attempt. Remaining criteria: ${PENDING}."
    if [ -n "$DYNAMIC_PROMPT" ]; then
      STAGE_MSG="${STAGE_MSG} Dynamic prompt: ${DYNAMIC_PROMPT}"
    fi
    ;;
  user_escalated)
    STAGE_MSG="[RTL Skill Completion Loop - escalation] ${SKILL_NAME} last_chance failed. User decision required. Remaining criteria: ${PENDING}."
    if [ -n "$DYNAMIC_PROMPT" ]; then
      STAGE_MSG="${STAGE_MSG} Suggested context: ${DYNAMIC_PROMPT}"
    fi
    ;;
  *)
    STAGE_MSG="[RTL Skill Completion Loop] ${SKILL_NAME} in progress. Remaining criteria: ${PENDING}."
    ;;
esac

printf '{"continue":false,"decision":"block","reason":"%s"}' "$(jsonu_escape "$STAGE_MSG")"
