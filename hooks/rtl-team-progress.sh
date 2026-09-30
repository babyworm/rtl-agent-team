#!/bin/sh
# Hook: PostToolUse:TaskUpdate — Team progress tracking
# Updates .rat/state/team-progress.json when team mode is active.
# In "Orchestrator as Teammate" pattern, the coordinator teammate and workers
# both trigger this hook via TaskUpdate calls.
# Shows progress summary in hook output.

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser

# Extract CWD from hook input (consistent with peer hooks)
INPUT=$(cat)
CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_DIR="$RAT_DIR/state"
TEAM_CONFIG="$STATE_DIR/team-config.json"
PROGRESS_FILE="$STATE_DIR/team-progress.json"

# Team activity keeps the config fresh: the 2h staleness bound (team-gate-util.sh)
# measures time since the team was last active. Only the recorded leader's session
# counts, and in-process teammates share it. TaskUpdate is not team-only, so another
# session's own task list must not keep an abandoned team alive.
if [ -f "$TEAM_CONFIG" ]; then
  _TP_SESSION=$(jsonu_session_id "$INPUT")  # a plain token, so never a placeholder leader
  if [ -n "$_TP_SESSION" ] && \
     [ "$_TP_SESSION" = "$(jsonu_get_file_path_string "$TEAM_CONFIG" "leader_session_id")" ]; then
    touch "$TEAM_CONFIG"
  fi
fi

# Only active during team mode
if [ ! -f "$TEAM_CONFIG" ]; then
  emit_post_continue
fi

# Check team_mode is true
_TEAM_MODE=$(jsonu_get_file_path_bool "$TEAM_CONFIG" "team_mode")
if [ "$_TEAM_MODE" != "true" ]; then
  emit_post_continue
fi

# Extract team name for display
_TEAM_NAME=$(jsonu_get_file_path_string "$TEAM_CONFIG" "team_name")

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

emit_post_continue
