#!/bin/sh
# RTL Audit Spawn Complete: PostToolUse:TaskCreate hook
# Records spawn_complete event in the audit trace after an agent is spawned.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

# Only handle rtl-agent-team agents
AGENT_TYPE=$(jsonu_get_input_string "$INPUT" "subagent_type")
[ -z "$AGENT_TYPE" ] && printf '{"continue":true}' && exit 0

case "$AGENT_TYPE" in
  rtl-agent-team:*)
    SHORT_NAME="${AGENT_TYPE#rtl-agent-team:}"
    ;;
  *)
    printf '{"continue":true}'
    exit 0
    ;;
esac

# Check if audit is initialized
_AUDIT_LIB="$SCRIPT_DIR/lib/audit-util.sh"
if [ ! -f "$_AUDIT_LIB" ]; then
  printf '{"continue":true}'
  exit 0
fi

. "$SCRIPT_DIR/lib/flock-util.sh"
. "$_AUDIT_LIB"

_SID=$(audit_session_id "$CWD")
if [ -z "$_SID" ] || [ ! -d "$CWD/.rtl-agent-team/audit/$_SID" ]; then
  printf '{"continue":true}'
  exit 0
fi

# Log spawn_complete event
_SAFE_AGENT=$(jsonu_escape "$SHORT_NAME")
audit_trace_append "$CWD" \
  "{\"event\":\"spawn_complete\",\"agent\":\"${_SAFE_AGENT}\",\"detail\":\"Agent ${_SAFE_AGENT} spawn completed\",\"status\":\"success\"}" \
  >/dev/null

printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[SPAWN OK] %s"}}' "$SHORT_NAME"
