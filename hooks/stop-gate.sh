#!/bin/sh
# Stop Gate: keeps Claude working while rat-auto-design runs, and auto-continues an
# ultraloop or a PPA-Opt loop within its time window.
# Supports escalation ladder:
#   primary attempts (<=N) -> fallback strategy (N+1..2N) -> last chance (2N+1) -> user escalation.
# A user decision (the orchestrator asks for one, the ladder is used up, or an upper-spec
# violation is unresolved) lets Claude stop and shows the user a notice once per chain.
#
# Every block goes through hooks/lib/stop-budget-util.sh (budget ids ultraloop, ppa-loop and
# autopilot): after RAT_STOP_BLOCK_LIMIT blocks without progress (a new loop cycle, or another
# gate or gate attempt recorded by the orchestrator) in one continuation chain, the gate lets
# Claude stop and shows the user a notice. From the chain's Stop STOPU_CHAIN_CAP + 1 on,
# whichever hooks blocked the earlier Stops, the gate shows the notice instead of blocking.

INPUT=$(cat)

# Load flock utility for concurrent access protection
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/stop-budget-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
. "$SCRIPT_DIR/lib/posix-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_root_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_FILE="$RAT_DIR/state/rat-auto-design-state.json"

# Legacy migration: rename old state file from pre-0.6.10 naming convention
LEGACY_STATE_FILE="$RAT_DIR/state/rtl-autopilot-state.json"
if [ ! -f "$STATE_FILE" ] && [ -f "$LEGACY_STATE_FILE" ]; then
  mv "$LEGACY_STATE_FILE" "$STATE_FILE"
fi

if teamu_should_skip_gate "$RAT_DIR/state" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$RAT_DIR/state" ultraloop ppa-loop autopilot)

# Let Claude stop once no loop and no autopilot run holds the stop. Every condition this
# gate checks is then satisfied, so all three budgets are reset (the chain's Stop count
# stays): a condition that comes back later in the chain is not left silent.
_allow_stop() {
  stopu_clear ultraloop "$RAT_DIR/state"
  stopu_clear ppa-loop "$RAT_DIR/state"
  stopu_clear autopilot "$RAT_DIR/state"
  emit_post_continue
}

# Ultraloop auto-continue: if ultraloop is active and within its time window, keep going
ULTRALOOP_STATE="$RAT_DIR/state/ultraloop-state.json"
if [ -f "$ULTRALOOP_STATE" ]; then
  UL_MODE=$(jsonu_get_file_path_string "$ULTRALOOP_STATE" "mode")
  if [ "$UL_MODE" = "ultraloop" ]; then
    UL_TIMESTAMP=$(jsonu_get_file_path_num "$ULTRALOOP_STATE" "last_cycle_timestamp")
    UL_MINUTES=$(jsonu_get_file_path_num "$ULTRALOOP_STATE" "auto_continue_minutes")
    [ -z "$UL_MINUTES" ] && UL_MINUTES=30
    UL_THRESHOLD=$((UL_MINUTES * 60))
    UL_ELAPSED=$(posix_elapsed_seconds "$UL_TIMESTAMP")
    if [ "$UL_ELAPSED" -lt "$UL_THRESHOLD" ]; then
      # Progress means a new cycle: the loop refreshes last_cycle_timestamp at each one.
      MSG="[Ultraloop] auto-continue: ${UL_ELAPSED}s elapsed (threshold=${UL_THRESHOLD}s). Continuing autonomous loop."
      stopu_gate ultraloop "$RAT_DIR/state" "$STOP_CHAIN" "ultraloop|$UL_TIMESTAMP" "$MSG" \
        "[Ultraloop] The loop is paused: automatic continuation stopped for this turn. Say continue to resume, or end the loop: rm $(shq "$ULTRALOOP_STATE")"
    fi
  fi
fi

# PPA-Opt loop auto-continue: if ppa-loop is active and within its time window, keep going
PPA_LOOP_STATE="$RAT_DIR/state/ppa-loop-state.json"
if [ -f "$PPA_LOOP_STATE" ]; then
  PPA_MODE=$(jsonu_get_file_path_string "$PPA_LOOP_STATE" "mode")
  if [ "$PPA_MODE" = "ppa-loop" ]; then
    PPA_TIMESTAMP=$(jsonu_get_file_path_num "$PPA_LOOP_STATE" "last_cycle_timestamp")
    PPA_MINUTES=$(jsonu_get_file_path_num "$PPA_LOOP_STATE" "auto_continue_minutes")
    [ -z "$PPA_MINUTES" ] && PPA_MINUTES=30
    PPA_THRESHOLD=$((PPA_MINUTES * 60))
    PPA_ELAPSED=$(posix_elapsed_seconds "$PPA_TIMESTAMP")
    if [ "$PPA_ELAPSED" -lt "$PPA_THRESHOLD" ]; then
      # Progress means a new cycle: the loop refreshes last_cycle_timestamp at each one.
      MSG="[PPA-Opt loop] auto-continue: ${PPA_ELAPSED}s elapsed (threshold=${PPA_THRESHOLD}s). Continuing PPA optimization loop."
      stopu_gate ppa-loop "$RAT_DIR/state" "$STOP_CHAIN" "ppa-loop|$PPA_TIMESTAMP" "$MSG" \
        "[PPA-Opt loop] The loop is paused: automatic continuation stopped for this turn. Say continue to resume, or end the loop: rm $(shq "$PPA_LOOP_STATE")"
    fi
  fi
fi

if [ ! -f "$STATE_FILE" ]; then
  _allow_stop
fi

# Staleness escape: an autopilot run that crashed or was abandoned leaves a
# non-"completed" state file behind. Without a bound it would block EVERY Stop
# in EVERY future session forever. Mirror the 2h bound used by
# rtl-skill-completion-gate.sh: if the state file has not been touched within
# the bound, treat the run as abandoned and allow the session to stop.
STOP_STALE_BOUND=${RAT_STOP_STALE_SECONDS:-7200}
STATE_MTIME=$(get_mtime_epoch "$STATE_FILE")
if [ -n "$STATE_MTIME" ]; then
  STATE_AGE=$(posix_elapsed_seconds "$STATE_MTIME")
  if [ "$STATE_AGE" -ge "$STOP_STALE_BOUND" ] 2>/dev/null; then
    _allow_stop
  fi
fi

STATUS=$(jsonu_get_file_path_string "$STATE_FILE" "status")
if [ "$STATUS" = "completed" ]; then
  _allow_stop
fi

UPPER_SPEC_BLOCKING=$(jsonu_get_file_path_bool "$STATE_FILE" "upper_spec_blocking")
if [ "$UPPER_SPEC_BLOCKING" = "true" ]; then
  # The user reads this notice, so it tells the user what to decide.
  MSG="[RAT Auto-Design STOP] Upper-spec violation is unresolved, so the pipeline is paused. Decide whether to approve the violation or send the pipeline back to fix it, then tell Claude."
  # A user decision: notify once per chain (limit 0), then stay silent.
  stopu_gate autopilot "$RAT_DIR/state" "$STOP_CHAIN" "upper-spec" "$MSG" "$MSG" 0
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
  # The ladder is used up: the user decides (the decision notice below).
  NEEDS_USER_DECISION=true
  [ -z "$STRATEGY" ] && STRATEGY="user_escalated"
fi

MSG="${MSG} (strategy=${STRATEGY}, primary=${PRIMARY_ATTEMPTS}, fallback=${FALLBACK_ATTEMPTS}, last_chance=${LAST_CHANCE_ATTEMPTS})"
# A user decision is the next step: let Claude stop and show the escalation to the
# user, once per chain (limit 0). The user reads this notice, and the orchestrator may
# ask at any ladder stage, so the notice carries none of that stage's instructions to Claude.
if [ "$NEEDS_USER_DECISION" = "true" ]; then
  DECISION_NOTICE="[RAT Auto-Design Loop ${ACTIVE_GATE_ID}] The gate needs your decision, so the pipeline is paused (strategy=${STRATEGY}, primary=${PRIMARY_ATTEMPTS}, fallback=${FALLBACK_ATTEMPTS}, last_chance=${LAST_CHANCE_ATTEMPTS})."
  if [ -n "$DYNAMIC_PROMPT_TEXT" ]; then
    # End the orchestrator's note as a sentence, so it cannot run into the user's action.
    case "$DYNAMIC_PROMPT_TEXT" in
      *[.?!]) DECISION_NOTE=$DYNAMIC_PROMPT_TEXT ;;
      *) DECISION_NOTE="${DYNAMIC_PROMPT_TEXT}." ;;
    esac
    DECISION_NOTICE="${DECISION_NOTICE} Orchestrator note: ${DECISION_NOTE}"
  fi
  DECISION_NOTICE="${DECISION_NOTICE} Tell Claude how to proceed."
  stopu_gate autopilot "$RAT_DIR/state" "$STOP_CHAIN" "user-decision|$ACTIVE_GATE_ID" "$DECISION_NOTICE" "$DECISION_NOTICE" 0
fi
# Progress means the orchestrator recorded another gate attempt.
stopu_gate autopilot "$RAT_DIR/state" "$STOP_CHAIN" \
  "$ACTIVE_GATE_ID|$PRIMARY_ATTEMPTS|$FALLBACK_ATTEMPTS|$LAST_CHANCE_ATTEMPTS" \
  "$MSG" \
  "[RAT Auto-Design Loop ${ACTIVE_GATE_ID}] The pipeline is paused: automatic continuation stopped for this turn. Say continue to resume."
