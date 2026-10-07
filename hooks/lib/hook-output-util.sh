#!/bin/sh
# hook-output-util.sh — Shared hook JSON output helpers.
# Requires: json-util.sh sourced and parser detected.
#
# Output contract (Claude Code hooks reference; verified live on CLI 2.1.282):
# a gate never sets the continue field to false. That field takes precedence
# over a Stop block and a PreToolUse deny, ends the turn, and drops the reason.
#   Stop block   {"decision":"block","reason":…}  Claude receives the reason and keeps working.
#   Stop notice  {"systemMessage":…}              Claude stops; the user sees the message.
#   Deny         hookSpecificOutput.permissionDecision "deny"  Only that tool call is refused.

# Emit a continue response with optional additionalContext message, then exit 0.
# PreToolUse only: a message rides in a PreToolUse envelope. After a tool ran, give
# context with emit_post_context; to allow any other event, use emit_post_continue.
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

# Refuse one tool call and give Claude the reason, then exit 0.
# Usage: emit_block "reason message"
emit_block() {
  _EB_MSG="$1"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$(jsonu_escape "$_EB_MSG")"
  exit 0
}

# Keep Claude working: block the stop and return the reason to Claude, then exit 0.
# Stop gates call this through stopu_gate (stop-budget-util.sh) so they cannot loop.
# Usage: emit_stop_block "reason message"
emit_stop_block() {
  _ESB_MSG="$1"
  printf '{"decision":"block","reason":"%s"}' "$(jsonu_escape "$_ESB_MSG")"
  exit 0
}

# Let Claude stop and show a message to the user, then exit 0.
# Use when the next step is the user's decision (waivers, approvals, escalations).
# Usage: emit_stop_notice "message for the user"
emit_stop_notice() {
  _ESN_MSG="$1"
  printf '{"systemMessage":"%s"}' "$(jsonu_escape "$_ESN_MSG")"
  exit 0
}

# Give Claude context after a tool ran (PostToolUse envelope), then exit 0.
# Usage: emit_post_context "message"   (an empty message emits a plain continue)
emit_post_context() {
  _EPC_MSG="$1"
  if [ -n "$_EPC_MSG" ]; then
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}' "$(jsonu_escape "$_EPC_MSG")"
  else
    printf '{"continue":true}'
  fi
  exit 0
}

# Emit a plain continue response (no additionalContext), then exit 0. Despite its
# name it is the plain allow for any event: PreToolUse hooks and Stop gates use it too.
# Usage: emit_post_continue
emit_post_continue() {
  printf '{"continue":true}'
  exit 0
}
