#!/bin/sh
# Stop Gate: block session exit while rtl-autopilot is running.
# Reads stdin JSON for cwd, checks if state file exists.

STATE_FILE=".rtl-agent-team/state/rtl-autopilot-state.json"

# Read stdin (hook input)
INPUT=$(cat)

# Extract cwd from JSON (portable: no jq dependency)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

if [ -f "$CWD/$STATE_FILE" ]; then
  printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"RTL Autopilot is still running. Complete all 5 phases or run /rtl-agent-team:cancel to stop."}}'
else
  printf '{"continue":true}'
fi
