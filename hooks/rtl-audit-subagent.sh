#!/bin/sh
# RTL Audit Subagent: SubagentStart/SubagentStop diagnostic hook
# Records SubagentStart and SubagentStop events to a diagnostic log.
# If these events are not supported by the Claude Code version, this hook
# simply never fires (registered but inactive — no harm).
#
# Phase 1: Diagnostic-only — captures raw stdin JSON for schema analysis.
# Phase 2 (future): Integrate with trace.jsonl after schema is confirmed.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/audit-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

# Only log for RTL projects with active audit sessions
AUDIT_DIR="$CWD/.rtl-agent-team/audit"
[ ! -d "$AUDIT_DIR" ] && exit 0

SESSION_ID=$(audit_session_id "$CWD")
[ -z "$SESSION_ID" ] && exit 0

SESSION_DIR="$AUDIT_DIR/$SESSION_ID"
[ ! -d "$SESSION_DIR" ] && exit 0

# Append raw input to diagnostic log for schema analysis
DIAG_FILE="$SESSION_DIR/subagent-debug.jsonl"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)

if acquire_lock "$DIAG_FILE"; then
  printf '{"ts":"%s","raw_input":%s}\n' "$TS" "$INPUT" >> "$DIAG_FILE"
  release_lock "$DIAG_FILE"
else
  # Fail-open: append without lock
  printf '{"ts":"%s","raw_input":%s}\n' "$TS" "$INPUT" >> "$DIAG_FILE"
fi

# No output — diagnostic only
