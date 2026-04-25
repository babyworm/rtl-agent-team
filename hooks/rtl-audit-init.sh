#!/bin/sh
# RTL Audit Init: SessionStart hook
# Initializes audit session directory for trace logging.
# Separate from rtl-orchestrator-inject.sh to maintain single responsibility.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
. "$SCRIPT_DIR/lib/audit-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

# Only initialize audit when RAT marker exists (.rat/ or legacy .rtl-agent-team/).
# Generic directories like rtl/ or docs/ are not RAT markers — they only become
# meaningful once a rtl-agent-team skill has been invoked at least once.
if ! rat_is_project "$CWD"; then
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}'
  exit 0
fi

# Initialize session and prune old sessions
if audit_init_session "$CWD"; then
  audit_prune "$CWD" "$AUDIT_MAX_SESSIONS"

  SESSION_ID=$(audit_session_id "$CWD")
  # Log session start event
  audit_trace_append "$CWD" \
    "{\"event\":\"session_start\",\"agent\":\"system\",\"detail\":\"Audit session initialized: ${SESSION_ID}\",\"status\":\"started\"}" \
    >/dev/null
fi

# Minimal valid SessionStart JSON to satisfy hook output schema
# (hookEventName is required by Claude Code's hook output validator).
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}'
