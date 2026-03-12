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

# Phase 6 stale detection helper (shared by Bash and Edit/Write paths)
_check_p6_stale() {
  _P6_CWD="$1"
  _P6_STATE="$2"
  _P6_REVIEW_DIR="$_P6_CWD/reviews/phase-6-review"
  # Only mark stale when Phase 6 was fully completed (explicit completion marker),
  # not just when any .md exists (which happens during in-progress P6 runs).
  _P6_DONE_MARKER="$_P6_STATE/cross-review-phase-6-done"
  if [ -f "$_P6_DONE_MARKER" ] || \
     { [ -f "$_P6_REVIEW_DIR/code-review.md" ] && [ -f "$_P6_REVIEW_DIR/design-review.md" ] && \
       ls "$_P6_REVIEW_DIR"/design-note*.md >/dev/null 2>&1 && [ -f "$_P6_REVIEW_DIR/improvements.md" ]; }; then
    touch "$_P6_STATE/phase6-stale"
    printf '%s' " Phase 6 review documents marked as stale — update code-review, design-review, design-note, and improvements after verification."
  fi
}

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
  # Extract first command and strip trailing & for classification.
  FIRST_CMD=$(printf '%s' "$COMMAND" | sed 's/^[[:space:]]*//' | awk '{print $1}')
  FIRST_CMD_BASE=$(basename "$FIRST_CMD" 2>/dev/null || printf '%s' "$FIRST_CMD")
  LINT_CHECK_CMD=$(printf '%s' "$COMMAND" | sed 's/[[:space:]]*&[[:space:]]*$//')
  # Mixed-command / write-intent check FIRST: skip all exemptions when detected.
  # This prevents read-only/lint prefixes from masking write operations.
  # Note: pipes (|) are NOT treated as mixed — both sides of a pipe are read-only
  # for RTL tracking purposes. fd redirections (2>&1) are stripped before & check.
  IS_MIXED=false
  case "$LINT_CHECK_CMD" in
    *"&&"*|*"||"*|*";"*) IS_MIXED=true ;;
  esac
  # Check for background & separately after stripping fd redirections (N>&M)
  if [ "$IS_MIXED" = "false" ]; then
    AMPERSAND_CHECK=$(printf '%s' "$LINT_CHECK_CMD" | sed 's/[0-9]*>&[0-9]*/  /g')
    case "$AMPERSAND_CHECK" in
      *"&"*) IS_MIXED=true ;;
    esac
  fi
  # Output redirection to RTL files is a write even from read-only commands
  # (e.g., cat /dev/null > rtl/top.sv). Check only when not already mixed.
  if [ "$IS_MIXED" = "false" ]; then
    case "$LINT_CHECK_CMD" in
      *">"*)
        if printf '%s' "$LINT_CHECK_CMD" | awk 'BEGIN{rc=1} />[> ]*[^ ]*\.(sv|svh|v|vh)([^a-zA-Z0-9_]|$)/{rc=0} END{exit rc}'; then
          IS_MIXED=true
        fi ;;
    esac
  fi
  if [ "$IS_MIXED" = "false" ]; then
    # Filter read-only commands (fail-closed: unknown commands are tracked).
    # find excluded: find -exec/-delete can write. Only safe single-command reads here.
    case "$FIRST_CMD_BASE" in
      cat|head|tail|less|more|grep|egrep|fgrep|rg|wc|file|stat|ls|diff|cmp|strings|hexdump|od|readlink|md5sum|sha256sum|sha1sum|cksum)
        printf '{"continue":true}'
        exit 0
        ;;
    esac
    # Token-aware lint-only exemption: only when first command IS a lint tool.
    case "$FIRST_CMD_BASE" in
      verilator)
        case "$LINT_CHECK_CMD" in *--lint-only*)
          printf '{"continue":true}'
          exit 0
        esac ;;
      verible-verilog-lint)
        printf '{"continue":true}'
        exit 0
        ;;
      slang)
        case "$LINT_CHECK_CMD" in *--lint-only*|*-W*)
          printf '{"continue":true}'
          exit 0
        esac ;;
    esac
  fi
  # Extract RTL file paths from command (POSIX-safe: awk tokenizer, no grep -oE or GNU sed)
  BASH_RTL_FILES=$(printf '%s' "$COMMAND" | awk '{
    gsub(/[;&<>|"'\''"]/, " ")
    n = split($0, tokens, " ")
    for (i = 1; i <= n; i++) {
      t = tokens[i]
      if (t ~ /\.(sv|svh|v|vh)$/) print t
    }
  }' | sort -u)
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
  if acquire_lock "$TRACK_FILE"; then
    rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
    printf '%s\n' "$BASH_RTL_FILES" | while IFS= read -r bf; do
      [ -z "$bf" ] && continue
      if ! grep -qxF "$bf" "$TRACK_FILE" 2>/dev/null; then
        printf '%s\n' "$bf" >> "$TRACK_FILE"
      fi
    done
    release_lock "$TRACK_FILE"
  else
    rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
    printf '%s\n' "$BASH_RTL_FILES" >> "$STATE_DIR/rtl-modified-files-fallback.txt"
  fi
  COUNT=$(cat "$TRACK_FILE" "$STATE_DIR/rtl-modified-files-fallback.txt" 2>/dev/null | wc -l | tr -d ' ')
  P6_MSG=$(_check_p6_stale "$CWD" "$STATE_DIR")
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
    if acquire_lock "$TRACK_FILE"; then
      rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
      if ! grep -qxF "$FILE_PATH" "$TRACK_FILE" 2>/dev/null; then
        printf '%s\n' "$FILE_PATH" >> "$TRACK_FILE"
      fi
      release_lock "$TRACK_FILE"
    else
      rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
      # Fail-closed: append to lock-free fallback queue (deduped at gate time)
      printf '%s\n' "$FILE_PATH" >> "$STATE_DIR/rtl-modified-files-fallback.txt"
    fi

    # Count tracked files
    COUNT=$(cat "$TRACK_FILE" "$STATE_DIR/rtl-modified-files-fallback.txt" 2>/dev/null | wc -l | tr -d ' ')
    BASENAME=$(basename "$FILE_PATH")

    P6_MSG=$(_check_p6_stale "$CWD" "$STATE_DIR")

    # Escape JSON-special characters in path/message variables
    SAFE_BASENAME=$(jsonu_escape "$BASENAME")
    SAFE_STATE_DIR=$(jsonu_escape "$STATE_DIR")
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[RTL Verify Gate] %s modified (%s unverified RTL files). After RTL modification you MUST: (1) create/update TB, (2) run cocotb/verilator functional simulation. Lint alone cannot guarantee functional correctness. When done: touch %s/rtl-verify-done%s"}}' "$SAFE_BASENAME" "$COUNT" "$SAFE_STATE_DIR" "$P6_MSG"
    ;;
  */docs/*|*/reviews/*)
    # Audit: log artifact_write for design documents
    _AUDIT_LIB="$SCRIPT_DIR/lib/audit-util.sh"
    if [ -f "$_AUDIT_LIB" ]; then
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
