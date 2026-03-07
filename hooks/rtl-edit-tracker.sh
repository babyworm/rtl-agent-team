#!/bin/sh
# RTL Edit Tracker: PostToolUse:Edit/Write hook
# Tracks modified .sv/.svh/.v/.vh files for verification enforcement.
# When an RTL file is edited, records it in a tracking file and injects
# a reminder that functional verification (not just lint) is required.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

# Load flock utility for concurrent access protection
. "$SCRIPT_DIR/lib/flock-util.sh"

# Extract file_path from tool input
FILE_PATH=$(jsonu_get_input_string "$INPUT" "file_path")

# B1: Bash command RTL detection
# When invoked as PostToolUse:Bash, file_path is absent — scan command string instead
if [ -z "$FILE_PATH" ]; then
  COMMAND=$(jsonu_get_input_string "$INPUT" "command")
  if [ -z "$COMMAND" ]; then
    printf '{"continue":true}'
    exit 0
  fi
  # Quick pass-through: no RTL extensions in command → minimal overhead
  if ! printf '%s' "$COMMAND" | grep -qE '\.(sv|svh|v|vh)([^a-zA-Z0-9_]|$)'; then
    printf '{"continue":true}'
    exit 0
  fi
  # Filter read-only commands to avoid false positives (fail-closed: unknown commands are tracked)
  FIRST_CMD=$(printf '%s' "$COMMAND" | sed 's/^[[:space:]]*//' | awk '{print $1}')
  FIRST_CMD_BASE=$(basename "$FIRST_CMD" 2>/dev/null || printf '%s' "$FIRST_CMD")
  case "$FIRST_CMD_BASE" in
    cat|head|tail|less|more|grep|egrep|fgrep|rg|wc|file|stat|ls|find|diff|cmp|strings|hexdump|od|readlink|md5sum|sha256sum|sha1sum|cksum)
      printf '{"continue":true}'
      exit 0
      ;;
  esac
  # Extract RTL file paths from command
  BASH_RTL_FILES=$(printf '%s' "$COMMAND" | grep -oE '[^ ;<>|"]+\.(sv|svh|v|vh)' 2>/dev/null | sort -u)
  if [ -z "$BASH_RTL_FILES" ]; then
    printf '{"continue":true}'
    exit 0
  fi
  STATE_DIR="$CWD/.rtl-agent-team/state"
  mkdir -p "$STATE_DIR"
  TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
  TEAM_CONFIG="$STATE_DIR/team-config.json"
  if [ -n "${CLAUDE_SESSION_ID:-}" ] && [ -f "$TEAM_CONFIG" ]; then
    TEAM_MODE=$(jsonu_get_file_path_bool "$TEAM_CONFIG" "team_mode")
    if [ "$TEAM_MODE" = "true" ]; then
      TRACK_FILE="$STATE_DIR/rtl-modified-files-${CLAUDE_SESSION_ID}.txt"
    fi
  fi
  # Invalidate previous verification evidence on any RTL edit (regardless of new/duplicate path)
  rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
  if acquire_lock "$TRACK_FILE"; then
    printf '%s\n' "$BASH_RTL_FILES" | while IFS= read -r bf; do
      [ -z "$bf" ] && continue
      if ! grep -qxF "$bf" "$TRACK_FILE" 2>/dev/null; then
        printf '%s\n' "$bf" >> "$TRACK_FILE"
      fi
    done
    release_lock "$TRACK_FILE"
  else
    printf '%s\n' "$BASH_RTL_FILES" >> "$STATE_DIR/rtl-modified-files-fallback.txt"
  fi
  COUNT=$(cat "$TRACK_FILE" "$STATE_DIR/rtl-modified-files-fallback.txt" 2>/dev/null | wc -l | tr -d ' ')
  P6_MSG=""
  P6_REVIEW_DIR="$CWD/reviews/phase-6-review"
  if [ -d "$P6_REVIEW_DIR" ] && ls "$P6_REVIEW_DIR"/*.md 2>/dev/null | grep -q .; then
    if acquire_lock "$STATE_DIR/phase6-stale"; then
      touch "$STATE_DIR/phase6-stale"
      release_lock "$STATE_DIR/phase6-stale"
    else
      touch "$STATE_DIR/phase6-stale"
    fi
    P6_MSG=" Phase 6 review documents marked as stale — update code-review and design-note after verification."
  fi
  SAFE_STATE_DIR=$(jsonu_escape "$STATE_DIR")
  printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[RTL Verify Gate] Bash command references RTL files (%s unverified). After RTL modification you MUST: (1) create/update TB, (2) run cocotb/verilator functional simulation. When done: touch %s/rtl-verify-done%s"}}' "$COUNT" "$SAFE_STATE_DIR" "$P6_MSG"
  exit 0
fi

# Check if the file is an RTL file
case "$FILE_PATH" in
  *.sv|*.svh|*.v|*.vh)
    STATE_DIR="$CWD/.rtl-agent-team/state"
    mkdir -p "$STATE_DIR"

    # Session-scoped tracking in team mode to prevent cross-worker file pollution
    TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
    TEAM_CONFIG="$STATE_DIR/team-config.json"
    if [ -n "${CLAUDE_SESSION_ID:-}" ] && [ -f "$TEAM_CONFIG" ]; then
      TEAM_MODE=$(jsonu_get_file_path_bool "$TEAM_CONFIG" "team_mode")
      if [ "$TEAM_MODE" = "true" ]; then
        TRACK_FILE="$STATE_DIR/rtl-modified-files-${CLAUDE_SESSION_ID}.txt"
      fi
    fi

    # Add file if not already tracked (locked for concurrent access)
    # Fail-closed: if lock fails, append without lock to prevent gate bypass
    # Invalidate previous verification evidence on any RTL edit (regardless of new/duplicate path)
    rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
    if acquire_lock "$TRACK_FILE"; then
      if ! grep -qxF "$FILE_PATH" "$TRACK_FILE" 2>/dev/null; then
        printf '%s\n' "$FILE_PATH" >> "$TRACK_FILE"
      fi
      release_lock "$TRACK_FILE"
    else
      # Fail-closed: append to lock-free fallback queue (deduped at gate time)
      printf '%s\n' "$FILE_PATH" >> "$STATE_DIR/rtl-modified-files-fallback.txt"
    fi

    # Count tracked files
    COUNT=$(cat "$TRACK_FILE" "$STATE_DIR/rtl-modified-files-fallback.txt" 2>/dev/null | wc -l | tr -d ' ')
    BASENAME=$(basename "$FILE_PATH")

    # Phase 6 stale detection: if a completed Phase 6 review exists, mark it stale
    # Protected by flock to prevent concurrent worker race conditions in team mode
    P6_MSG=""
    P6_REVIEW_DIR="$CWD/reviews/phase-6-review"
    if [ -d "$P6_REVIEW_DIR" ] && ls "$P6_REVIEW_DIR"/*.md 2>/dev/null | grep -q .; then
      if acquire_lock "$STATE_DIR/phase6-stale"; then
        touch "$STATE_DIR/phase6-stale"
        release_lock "$STATE_DIR/phase6-stale"
      else
        # Fail-closed: mark stale even if lock acquisition fails
        touch "$STATE_DIR/phase6-stale"
      fi
      P6_MSG=" Phase 6 review documents marked as stale — update code-review and design-note after verification."
    fi

    # Escape JSON-special characters in path/message variables
    SAFE_BASENAME=$(jsonu_escape "$BASENAME")
    SAFE_STATE_DIR=$(jsonu_escape "$STATE_DIR")
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[RTL Verify Gate] %s modified (%s unverified RTL files). After RTL modification you MUST: (1) create/update TB, (2) run cocotb/verilator functional simulation. Lint alone cannot guarantee functional correctness. When done: touch %s/rtl-verify-done%s"}}' "$SAFE_BASENAME" "$COUNT" "$SAFE_STATE_DIR" "$P6_MSG"
    ;;
  */docs/*|*/reviews/*)
    # Audit: log artifact_write for design documents
    _AUDIT_LIB="$SCRIPT_DIR/lib/audit-util.sh"
    if [ -f "$_AUDIT_LIB" ]; then
      . "$SCRIPT_DIR/lib/flock-util.sh"
      . "$_AUDIT_LIB"
      _ART_SID=$(audit_session_id "$CWD")
      if [ -n "$_ART_SID" ] && [ -d "$CWD/.rtl-agent-team/audit/$_ART_SID" ]; then
        _ART_SAFE=$(jsonu_escape "$FILE_PATH")
        audit_trace_append "$CWD" \
          "{\"event\":\"artifact_write\",\"agent\":\"system\",\"detail\":\"${_ART_SAFE}\",\"status\":\"success\"}" \
          >/dev/null
      fi
    fi
    printf '{"continue":true}'
    ;;
  *)
    # Not an RTL file, no action needed
    printf '{"continue":true}'
    ;;
esac
