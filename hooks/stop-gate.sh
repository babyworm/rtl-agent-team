#!/bin/sh
# Stop Gate: block session exit while rtl-autopilot is running.
# Supports escalation ladder:
#   primary attempts (<=N) -> fallback strategy (N+1..2N) -> last chance (2N+1) -> user escalation.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

# Load flock utility for concurrent access protection
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"

STATE_FILE="$CWD/.rtl-agent-team/state/rtl-autopilot-state.json"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

# Path-scoped JSON extraction avoids ambiguous key collisions when schema grows.
# Preference order: jq -> python3 JSON parser -> legacy flat-key fallback.
# Legacy fallback assumes key uniqueness and should only be used in constrained environments.
HAS_JQ=0
if command -v jq >/dev/null 2>&1; then
  HAS_JQ=1
fi

HAS_PYTHON3=0
if command -v python3 >/dev/null 2>&1; then
  HAS_PYTHON3=1
fi

build_jq_path_query() {
  path="$1"
  query=''
  while :; do
    segment=${path%%.*}
    query="$query.\"$segment\""
    if [ "$path" = "$segment" ]; then
      break
    fi
    path=${path#*.}
  done
  printf '%s' "$query"
}

legacy_get_string() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$STATE_FILE" | head -n 1
}

legacy_get_bool() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p" "$STATE_FILE" | head -n 1
}

legacy_get_num() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p" "$STATE_FILE" | head -n 1
}

get_path_string() {
  path="$1"
  if [ "$HAS_JQ" -eq 1 ]; then
    query=$(build_jq_path_query "$path")
    jq -r "($query // empty) | if . == null then \"\" else tostring end" "$STATE_FILE" 2>/dev/null | head -n 1
    return
  fi

  if [ "$HAS_PYTHON3" -eq 1 ]; then
    python3 - "$STATE_FILE" "$path" 2>/dev/null <<'PY'
import json
import sys

state_file = sys.argv[1]
path = sys.argv[2].split(".")

try:
    with open(state_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            print("")
            raise SystemExit(0)
        node = node[key]
    if node is None:
        print("")
    elif isinstance(node, bool):
        print("true" if node else "false")
    else:
        print(str(node))
except Exception:
    print("")
PY
    return
  fi

  # Legacy fallback (best-effort flat-key parse only).
  legacy_get_string "${path##*.}"
}

get_path_bool() {
  path="$1"
  if [ "$HAS_JQ" -eq 1 ]; then
    query=$(build_jq_path_query "$path")
    jq -r "($query // null) as \$v | if (\$v|type)==\"boolean\" then (if \$v then \"true\" else \"false\" end) else \"\" end" "$STATE_FILE" 2>/dev/null | head -n 1
    return
  fi

  if [ "$HAS_PYTHON3" -eq 1 ]; then
    python3 - "$STATE_FILE" "$path" 2>/dev/null <<'PY'
import json
import sys

state_file = sys.argv[1]
path = sys.argv[2].split(".")

try:
    with open(state_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            print("")
            raise SystemExit(0)
        node = node[key]
    if isinstance(node, bool):
        print("true" if node else "false")
    else:
        print("")
except Exception:
    print("")
PY
    return
  fi

  legacy_get_bool "${path##*.}"
}

get_path_num() {
  path="$1"
  if [ "$HAS_JQ" -eq 1 ]; then
    query=$(build_jq_path_query "$path")
    jq -r "($query // null) as \$v | if (\$v|type)==\"number\" then (\$v|floor|tostring) else \"\" end" "$STATE_FILE" 2>/dev/null | head -n 1
    return
  fi

  if [ "$HAS_PYTHON3" -eq 1 ]; then
    python3 - "$STATE_FILE" "$path" 2>/dev/null <<'PY'
import json
import sys

state_file = sys.argv[1]
path = sys.argv[2].split(".")

try:
    with open(state_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            print("")
            raise SystemExit(0)
        node = node[key]
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        print(str(int(node)))
    else:
        print("")
except Exception:
    print("")
PY
    return
  fi

  legacy_get_num "${path##*.}"
}

# Team-awareness: if running inside a team and not the leader, skip this gate.
TEAM_CONFIG="$CWD/.rtl-agent-team/state/team-config.json"
if [ -f "$TEAM_CONFIG" ]; then
  _TEAM_MODE=$(sed -n 's/.*"team_mode"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' "$TEAM_CONFIG" | head -n 1)
  _LEADER_ID=$(sed -n 's/.*"leader_session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)
  if [ "$_TEAM_MODE" = "true" ]; then
    # Staleness check: remove team-config older than 2 hours
    _TC_CREATED=$(sed -n 's/.*"created_at"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)
    _TC_STALE=false
    if [ -n "$_TC_CREATED" ]; then
      _TC_START=$(date -d "$_TC_CREATED" +%s 2>/dev/null || echo "")
      _TC_NOW=$(date +%s 2>/dev/null || echo "")
      if [ -n "$_TC_START" ] && [ -n "$_TC_NOW" ]; then
        _TC_AGE=$(( _TC_NOW - _TC_START ))
        if [ "$_TC_AGE" -gt 7200 ]; then
          rm -f "$TEAM_CONFIG"
          _TC_STALE=true
        fi
      fi
    fi
    if [ "$_TC_STALE" = "false" ]; then
      if [ -z "$_LEADER_ID" ] || [ "$_LEADER_ID" != "${CLAUDE_SESSION_ID:-}" ]; then
        printf '{"continue":true}'
        exit 0
      fi
    fi
  fi
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
  MSG="[RTL Autopilot STOP] Upper-spec violation is unresolved. Resolve violation or obtain user approval before proceeding."
  printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(json_escape "$MSG")"
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
