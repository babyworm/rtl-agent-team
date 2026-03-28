#!/bin/sh
# Shared team-mode guard for stop hooks.
# Requires json-util.sh to be sourced and parser mode initialized.
#
# In "Orchestrator as Teammate" pattern, the coordinator is a teammate (not a subagent).
# The coordinator's session ID differs from the leader's, so it bypasses stop gates
# just like worker sessions. Only the leader session is subject to stop enforcement.
#
# teamu_should_skip_gate <state_dir>
# Returns:
#   0 -> caller should skip stop-gate logic (coordinator/worker session in team mode)
#   1 -> caller should continue normal stop-gate logic

teamu_should_skip_gate() {
  TEAMU_STATE_DIR="$1"
  TEAMU_CONFIG="$TEAMU_STATE_DIR/team-config.json"

  if [ ! -f "$TEAMU_CONFIG" ]; then
    return 1
  fi

  TEAMU_MODE=$(jsonu_get_file_path_bool "$TEAMU_CONFIG" "team_mode")
  if [ "$TEAMU_MODE" != "true" ]; then
    return 1
  fi

  TEAMU_LEADER=$(jsonu_get_file_path_string "$TEAMU_CONFIG" "leader_session_id")
  TEAMU_CREATED=$(jsonu_get_file_path_string "$TEAMU_CONFIG" "created_at")
  if [ -n "$TEAMU_CREATED" ]; then
    TEAMU_START=$(date -d "$TEAMU_CREATED" +%s 2>/dev/null \
      || TZ=UTC date -jf "%Y-%m-%dT%H:%M:%S" "${TEAMU_CREATED%Z}" +%s 2>/dev/null \
      || echo "")
    TEAMU_NOW=$(date +%s 2>/dev/null || echo "")
    if [ -n "$TEAMU_START" ] && [ -n "$TEAMU_NOW" ]; then
      if [ $(( TEAMU_NOW - TEAMU_START )) -gt 7200 ]; then
        # Re-check created_at to reduce TOCTOU window with concurrent fresh writes
        _CURRENT_CREATED=$(jsonu_get_file_path_string "$TEAMU_CONFIG" "created_at")
        if [ "$_CURRENT_CREATED" = "$TEAMU_CREATED" ]; then
          rm -f "$TEAMU_CONFIG"
        fi
        return 1
      fi
    fi
  fi

  # Fail-closed: empty leader = unknown ownership → enforce gate for all sessions
  if [ -z "$TEAMU_LEADER" ]; then
    return 1
  fi
  # Known leader: skip gate only for worker sessions (non-leader)
  if [ "$TEAMU_LEADER" != "${CLAUDE_SESSION_ID:-}" ]; then
    return 0
  fi
  return 1
}
