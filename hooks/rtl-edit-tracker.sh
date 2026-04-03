#!/bin/sh
# RTL Edit Tracker: PostToolUse:Edit/Write/Bash hook
# Tracks modified .sv/.svh/.v/.vh files for verification enforcement.
# When an RTL file is edited, records it in a tracking file and injects
# a reminder that functional verification (not just lint) is required.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

# Load flock utility for concurrent access protection
. "$SCRIPT_DIR/lib/flock-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }

# --- Shared helpers (used by both Bash and Edit/Write paths) ---

# Phase 6 stale detection helper
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

# Set up STATE_DIR and TRACK_FILE with team mode awareness.
# Sets globals: STATE_DIR, TRACK_FILE
_setup_tracking() {
  STATE_DIR="$RAT_DIR/state"
  mkdir -p "$STATE_DIR"
  TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
  _ST_TEAM_CONFIG="$STATE_DIR/team-config.json"
  if [ -n "${CLAUDE_SESSION_ID:-}" ] && [ -f "$_ST_TEAM_CONFIG" ]; then
    _ST_TEAM_MODE=$(jsonu_get_file_path_bool "$_ST_TEAM_CONFIG" "team_mode")
    if [ "$_ST_TEAM_MODE" = "true" ]; then
      TRACK_FILE="$STATE_DIR/rtl-modified-files-${CLAUDE_SESSION_ID}.txt"
    fi
  fi
}

# Track file(s) with locking and verify marker invalidation.
# Accepts newline-separated file paths via $1.
_track_and_invalidate() {
  _TI_FILES="$1"
  if acquire_lock "$TRACK_FILE"; then
    rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
    printf '%s\n' "$_TI_FILES" | while IFS= read -r _ti_f; do
      [ -z "$_ti_f" ] && continue
      if ! grep -qxF "$_ti_f" "$TRACK_FILE" 2>/dev/null; then
        printf '%s\n' "$_ti_f" >> "$TRACK_FILE"
      fi
    done
    release_lock "$TRACK_FILE"
  else
    rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
    printf '%s\n' "$_TI_FILES" >> "$STATE_DIR/rtl-modified-files-fallback.txt"
  fi
}

# Compute count and P6 stale message. Sets globals: COUNT, P6_MSG, SAFE_STATE_DIR
_prepare_gate_output() {
  COUNT=$(cat "$TRACK_FILE" "$STATE_DIR/rtl-modified-files-fallback.txt" 2>/dev/null | wc -l | tr -d ' ')
  P6_MSG=$(_check_p6_stale "$CWD" "$STATE_DIR")
  SAFE_STATE_DIR=$(jsonu_escape "$STATE_DIR")
}

# --- End shared helpers ---

# Extract file_path from tool input
FILE_PATH=$(jsonu_get_input_string "$INPUT" "file_path")

# B1: Bash command RTL detection
# When invoked as PostToolUse:Bash, file_path is absent — scan command string instead
if [ -z "$FILE_PATH" ]; then
  COMMAND=$(jsonu_get_input_string "$INPUT" "command")
  if [ -z "$COMMAND" ]; then
    emit_post_continue
  fi
  # Quick pass-through: no RTL extensions in command → minimal overhead
  if ! printf '%s' "$COMMAND" | grep -qE '\.(sv|svh|v|vh)([^a-zA-Z0-9_]|$)'; then
    emit_post_continue
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
        emit_post_continue
        ;;
    esac
    # Token-aware lint-only exemption: only when first command IS a lint tool.
    case "$FIRST_CMD_BASE" in
      verilator)
        case "$LINT_CHECK_CMD" in *--lint-only*)
          emit_post_continue
        esac ;;
      verible-verilog-lint)
        emit_post_continue
        ;;
      slang)
        case "$LINT_CHECK_CMD" in *--lint-only*|*-W*)
          emit_post_continue
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
    emit_post_continue
  fi
  _setup_tracking
  _track_and_invalidate "$BASH_RTL_FILES"
  _prepare_gate_output
  printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[RTL Verify Gate] Bash command references RTL files (%s unverified). After RTL modification you MUST: (1) create/update TB, (2) run cocotb/verilator functional simulation. When done: touch %s/rtl-verify-done%s"}}' "$COUNT" "$SAFE_STATE_DIR" "$P6_MSG"
  exit 0
fi

# Check if the file is an RTL file
case "$FILE_PATH" in
  *.sv|*.svh|*.v|*.vh)
    _setup_tracking
    _track_and_invalidate "$FILE_PATH"
    _prepare_gate_output
    SAFE_BASENAME=$(jsonu_escape "$(basename "$FILE_PATH")")
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[RTL Verify Gate] %s modified (%s unverified RTL files). After RTL modification you MUST: (1) create/update TB, (2) run cocotb/verilator functional simulation. Lint alone cannot guarantee functional correctness. When done: touch %s/rtl-verify-done%s"}}' "$SAFE_BASENAME" "$COUNT" "$SAFE_STATE_DIR" "$P6_MSG"
    ;;
  */sim/*.py)
    # Testbench Python file modified — invalidate previous verification results
    _setup_tracking
    if acquire_lock "$TRACK_FILE"; then
      rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
      release_lock "$TRACK_FILE"
    else
      rm -f "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
    fi
    SAFE_TB=$(jsonu_escape "$(basename "$FILE_PATH")")
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[TB Verify Gate] Testbench %s modified — previous verification results invalidated. Re-run functional verification to confirm RTL correctness with updated tests."}}\n' "$SAFE_TB"
    exit 0
    ;;
  */docs/phase-1-research/*|*/docs/phase-2-architecture/*|*/docs/phase-3-uarch/*)
    # Spec Change Cascade: upstream phase doc modified → check downstream staleness
    _CASCADE_WARN=""
    _CASCADE_PHASE=""
    _CASCADE_DOWNSTREAM=""
    case "$FILE_PATH" in
      */docs/phase-1-research/*) _CASCADE_PHASE=1; _CASCADE_DOWNSTREAM="P2, P3, P4, P5" ;;
      */docs/phase-2-architecture/*) _CASCADE_PHASE=2; _CASCADE_DOWNSTREAM="P3, P4, P5" ;;
      */docs/phase-3-uarch/*) _CASCADE_PHASE=3; _CASCADE_DOWNSTREAM="P4, P5" ;;
    esac
    if [ -n "$_CASCADE_PHASE" ]; then
      _HAS_DOWNSTREAM=false
      case "$_CASCADE_PHASE" in
        1|2)
          [ -d "$CWD/docs/phase-3-uarch" ] && [ -n "$(ls "$CWD/docs/phase-3-uarch/" 2>/dev/null)" ] && _HAS_DOWNSTREAM=true
          ;;
      esac
      if [ "$_HAS_DOWNSTREAM" = "false" ]; then
        [ -d "$CWD/rtl" ] && [ -n "$(ls "$CWD/rtl/" 2>/dev/null)" ] && _HAS_DOWNSTREAM=true
      fi
      if [ "$_HAS_DOWNSTREAM" = "true" ]; then
        _setup_tracking
        _CASCADE_SEV="WARNING"
        case "$FILE_PATH" in *.json) _CASCADE_SEV="CRITICAL" ;; esac
        mkdir -p "$STATE_DIR"
        touch "$STATE_DIR/spec-cascade-stale-p${_CASCADE_PHASE}"
        _CASCADE_WARN="[SPEC CASCADE ${_CASCADE_SEV}] Phase ${_CASCADE_PHASE} document modified. Downstream artifacts (${_CASCADE_DOWNSTREAM}) may be inconsistent. Run /rtl-agent-team:cross-phase-contract-validator to verify."
      fi
    fi
    # Audit: log artifact_write
    _AUDIT_LIB="$SCRIPT_DIR/lib/audit-util.sh"
    if [ -f "$_AUDIT_LIB" ]; then
      . "$_AUDIT_LIB"
      _ART_SID=$(audit_session_id "$CWD")
      if [ -n "$_ART_SID" ] && [ -d "$RAT_DIR/audit/$_ART_SID" ]; then
        _ART_SAFE=$(jsonu_escape "$FILE_PATH")
        audit_trace_append "$CWD" \
          "{\"event\":\"artifact_write\",\"agent\":\"system\",\"detail\":\"${_ART_SAFE}\",\"status\":\"success\"}" \
          >/dev/null
      fi
    fi
    if [ -n "$_CASCADE_WARN" ]; then
      _SAFE_WARN=$(printf '%s' "$_CASCADE_WARN" | sed 's/"/\\"/g')
      printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$_SAFE_WARN"
      exit 0
    fi
    emit_post_continue
    ;;
  */docs/*|*/reviews/*)
    # Non-phase docs/reviews: audit only
    _AUDIT_LIB="$SCRIPT_DIR/lib/audit-util.sh"
    if [ -f "$_AUDIT_LIB" ]; then
      . "$_AUDIT_LIB"
      _ART_SID=$(audit_session_id "$CWD")
      if [ -n "$_ART_SID" ] && [ -d "$RAT_DIR/audit/$_ART_SID" ]; then
        _ART_SAFE=$(jsonu_escape "$FILE_PATH")
        audit_trace_append "$CWD" \
          "{\"event\":\"artifact_write\",\"agent\":\"system\",\"detail\":\"${_ART_SAFE}\",\"status\":\"success\"}" \
          >/dev/null
      fi
    fi
    emit_post_continue
    ;;
  *)
    # Not an RTL file, no action needed
    emit_post_continue
    ;;
esac
