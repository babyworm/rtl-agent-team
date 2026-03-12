#!/bin/sh
# hook-output-util.sh — Shared hook JSON output helpers.
# Requires: json-util.sh sourced and parser detected.

# Emit a continue response with optional additionalContext message, then exit 0.
# Usage: emit_continue "message"   or   emit_continue ""
emit_continue() {
  _EC_MSG="$1"
  if [ -n "$_EC_MSG" ]; then
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"%s"}}' "$(jsonu_escape "$_EC_MSG")"
  else
    printf '{"continue":true}'
  fi
  exit 0
}

# Emit a block/deny response with reason message, then exit 0.
# Usage: emit_block "reason message"
emit_block() {
  _EB_MSG="$1"
  printf '{"continue":false,"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$(jsonu_escape "$_EB_MSG")"
  exit 0
}
