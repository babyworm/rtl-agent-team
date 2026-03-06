#!/bin/sh
# Hook: PostToolUse:TaskUpdate — Team progress tracking
# Updates .rtl-agent-team/state/team-progress.json when team mode is active.
# In "Orchestrator as Teammate" pattern, the coordinator teammate and workers
# both trigger this hook via TaskUpdate calls.
# Shows progress summary in hook output.

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/flock-util.sh"

# Extract CWD from hook input (consistent with peer hooks)
INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
TEAM_CONFIG="$STATE_DIR/team-config.json"
PROGRESS_FILE="$STATE_DIR/team-progress.json"

# Only active during team mode
if [ ! -f "$TEAM_CONFIG" ]; then
  exit 0
fi

# Check team_mode is true (consistent sed pattern with peer hooks)
_TEAM_MODE=$(sed -n 's/.*"team_mode"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' "$TEAM_CONFIG" | head -n 1)
if [ "$_TEAM_MODE" != "true" ]; then
  exit 0
fi

# Extract team name for display
_TEAM_NAME=$(sed -n 's/.*"team_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)

# Update timestamp in progress file (locked to prevent concurrent write races)
if [ -f "$PROGRESS_FILE" ]; then
  _NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
  if acquire_lock "$PROGRESS_FILE"; then
    sed "s/\"last_updated\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"last_updated\": \"$_NOW\"/" "$PROGRESS_FILE" > "$PROGRESS_FILE.tmp" 2>/dev/null
    if [ -s "$PROGRESS_FILE.tmp" ]; then
      mv "$PROGRESS_FILE.tmp" "$PROGRESS_FILE"
    fi
    rm -f "$PROGRESS_FILE.tmp" 2>/dev/null
    release_lock "$PROGRESS_FILE"
  fi
fi

exit 0
