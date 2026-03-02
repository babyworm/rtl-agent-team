#!/bin/sh
# Stop Gate: block session exit while rtl-autopilot is running.
# Reads stdin JSON for cwd, checks if state file exists.

# Read stdin (hook input)
INPUT=$(cat)

# Extract cwd from JSON (portable: no jq dependency)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_FILE="$CWD/.rtl-agent-team/state/rtl-autopilot-state.json"

if [ -f "$STATE_FILE" ]; then
  printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"RTL Autopilot is still running. Complete all 6 phases or remove .rtl-agent-team/state/rtl-autopilot-state.json to stop."}}'
else
  printf '{"continue":true}'
fi
