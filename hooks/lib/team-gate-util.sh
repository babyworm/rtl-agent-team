#!/bin/sh
# Shared team-mode helpers for hooks.
# Requires json-util.sh (parser mode initialized) and posix-util.sh to be sourced.
#
# In "Orchestrator as Teammate" pattern, the coordinator is a teammate (not a subagent).
# The coordinator's session ID differs from the leader's, so it bypasses stop gates
# just like worker sessions. Only the leader session is subject to stop enforcement.
#
# teamu_config_is_stale <state_dir>
# Returns 0 when team-config.json exists and was last written over 2h ago, after
# removing it (unless a concurrent write refreshed it meanwhile); 1 otherwise.
# Every team check treats a stale config as no team mode.
#
# teamu_should_skip_gate <state_dir> <hook-input>
# Returns:
#   0 -> caller should skip stop-gate logic (coordinator/worker session in team mode)
#   1 -> caller should continue normal stop-gate logic

teamu_config_is_stale() {
  TEAMU_STALE_CONFIG="$1/team-config.json"
  [ -f "$TEAMU_STALE_CONFIG" ] || return 1
  # The age is the file's own mtime: the model-written created_at can be missing,
  # a placeholder, or local time.
  TEAMU_MTIME=$(get_mtime_epoch "$TEAMU_STALE_CONFIG")
  if [ -z "$TEAMU_MTIME" ] || [ "$(posix_elapsed_seconds "$TEAMU_MTIME")" -le 7200 ]; then
    return 1
  fi
  # Re-check the mtime to reduce TOCTOU window with concurrent fresh writes
  if [ "$(get_mtime_epoch "$TEAMU_STALE_CONFIG")" = "$TEAMU_MTIME" ]; then
    rm -f "$TEAMU_STALE_CONFIG"
  fi
  return 0
}

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

  if teamu_config_is_stale "$TEAMU_STATE_DIR"; then
    return 1
  fi

  # Fail-closed: an empty or placeholder leader, or an unknown session, enforces
  # the gate for every session.
  TEAMU_LEADER=$(jsonu_get_file_path_string "$TEAMU_CONFIG" "leader_session_id")
  case "$TEAMU_LEADER" in ''|*'<'*|*'$'*) return 1 ;; esac
  TEAMU_SESSION=$(jsonu_session_id "${2:-}")
  [ -n "$TEAMU_SESSION" ] || return 1
  # Known leader: skip the gate only for other sessions (coordinator, workers).
  [ "$TEAMU_LEADER" != "$TEAMU_SESSION" ]
}
