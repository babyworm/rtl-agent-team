#!/bin/sh
# audit-util.sh — POSIX sh audit logging utility for RTL Agent Team hooks.
#
# Provides append-only trace logging, prompt capture, and session management.
# Follows the same patterns as json-util.sh and flock-util.sh.
#
# Requires: json-util.sh sourced and parser detected, flock-util.sh sourced.
#
# Usage:
#   . "$SCRIPT_DIR/lib/audit-util.sh"
#   audit_init_session "$CWD"
#   SEQ=$(audit_trace_append "$CWD" '{"event":"skill_invoke","agent":"spec-analyst"}')
#   audit_save_prompt "$CWD" "$SEQ" "spec-analyst" "Analyze the spec..."
#   audit_prune "$CWD" 10

# Session ID: prefer CLAUDE_SESSION_ID, fallback to timestamp+PID.
_AUDIT_SESSION_ID_CACHE=""

AUDIT_MAX_SESSIONS=${AUDIT_MAX_SESSIONS:-10}
AUDIT_MAX_SIZE_MB=${AUDIT_MAX_SIZE_MB:-50}

# Return the current session ID (cached after first call).
audit_session_id() {
  _ASI_CWD="$1"
  if [ -n "$_AUDIT_SESSION_ID_CACHE" ]; then
    printf '%s' "$_AUDIT_SESSION_ID_CACHE"
    return 0
  fi

  _ASI_ID_FILE="$_ASI_CWD/.rtl-agent-team/audit/session-id.txt"
  if [ -f "$_ASI_ID_FILE" ]; then
    _AUDIT_SESSION_ID_CACHE=$(cat "$_ASI_ID_FILE" 2>/dev/null)
    printf '%s' "$_AUDIT_SESSION_ID_CACHE"
    return 0
  fi

  # Generate new ID
  if [ -n "${CLAUDE_SESSION_ID:-}" ]; then
    _AUDIT_SESSION_ID_CACHE="$CLAUDE_SESSION_ID"
  else
    _AUDIT_SESSION_ID_CACHE="$(date +%Y%m%d_%H%M%S)_$$"
  fi
  printf '%s' "$_AUDIT_SESSION_ID_CACHE"
}

# Initialize audit session directory and cache session ID.
# Returns 0 on success, 1 if not an RTL project.
audit_init_session() {
  _AIS_CWD="$1"
  _AIS_STATE="$_AIS_CWD/.rtl-agent-team"

  # Only initialize if this looks like an RTL project
  if [ ! -d "$_AIS_STATE" ] && [ ! -d "$_AIS_CWD/rtl" ] && [ ! -d "$_AIS_CWD/docs" ]; then
    return 1
  fi

  _AIS_ID=$(audit_session_id "$_AIS_CWD")
  _AIS_AUDIT_DIR="$_AIS_STATE/audit"
  _AIS_SESSION_DIR="$_AIS_AUDIT_DIR/$_AIS_ID"

  mkdir -p "$_AIS_SESSION_DIR/prompts"

  # Cache session ID to file
  printf '%s' "$_AIS_ID" > "$_AIS_AUDIT_DIR/session-id.txt"

  return 0
}

# Append a trace event to trace.jsonl. Adds ts and seq automatically.
# Usage: SEQ=$(audit_trace_append "$CWD" '{"event":"spawn_start","agent":"foo"}')
# The input JSON must NOT include ts or seq — they are prepended.
# Returns the sequence number on stdout.
audit_trace_append() {
  _ATA_CWD="$1"
  _ATA_JSON="$2"
  _ATA_ID=$(audit_session_id "$_ATA_CWD")

  if [ -z "$_ATA_ID" ]; then
    printf '0'
    return 1
  fi

  _ATA_TRACE="$_ATA_CWD/.rtl-agent-team/audit/$_ATA_ID/trace.jsonl"
  mkdir -p "$(dirname "$_ATA_TRACE")"

  # Generate timestamp
  _ATA_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)

  # Atomic seq generation + append under lock
  _ATA_SEQ=0
  if acquire_lock "$_ATA_TRACE"; then
    # Count existing lines for seq number
    if [ -f "$_ATA_TRACE" ]; then
      _ATA_SEQ=$(wc -l < "$_ATA_TRACE" | tr -d ' ')
    fi
    _ATA_SEQ=$((_ATA_SEQ + 1))

    # Merge ts and seq into the JSON object
    # Strip leading { from input, prepend ts+seq fields
    _ATA_BODY=$(printf '%s' "$_ATA_JSON" | sed 's/^[[:space:]]*{//')
    printf '{"ts":"%s","seq":%s,%s\n' "$_ATA_TS" "$_ATA_SEQ" "$_ATA_BODY" >> "$_ATA_TRACE"

    release_lock "$_ATA_TRACE"
  else
    # Fallback: append without lock (better than losing the event)
    if [ -f "$_ATA_TRACE" ]; then
      _ATA_SEQ=$(wc -l < "$_ATA_TRACE" | tr -d ' ')
    fi
    _ATA_SEQ=$((_ATA_SEQ + 1))
    _ATA_BODY=$(printf '%s' "$_ATA_JSON" | sed 's/^[[:space:]]*{//')
    printf '{"ts":"%s","seq":%s,%s\n' "$_ATA_TS" "$_ATA_SEQ" "$_ATA_BODY" >> "$_ATA_TRACE"
  fi

  printf '%s' "$_ATA_SEQ"
}

# Save an agent prompt to the prompts directory.
# Usage: audit_save_prompt "$CWD" "$SEQ" "agent-name" "prompt content"
audit_save_prompt() {
  _ASP_CWD="$1"
  _ASP_SEQ="$2"
  _ASP_AGENT="$3"
  _ASP_CONTENT="$4"
  _ASP_ID=$(audit_session_id "$_ASP_CWD")

  if [ -z "$_ASP_ID" ] || [ -z "$_ASP_CONTENT" ]; then
    return 1
  fi

  _ASP_DIR="$_ASP_CWD/.rtl-agent-team/audit/$_ASP_ID/prompts"
  mkdir -p "$_ASP_DIR"

  # Zero-pad seq to 3 digits
  _ASP_PAD=$(printf '%03d' "$_ASP_SEQ" 2>/dev/null || printf '%s' "$_ASP_SEQ")
  _ASP_FILE="$_ASP_DIR/${_ASP_PAD}_${_ASP_AGENT}.md"

  printf '%s\n' "$_ASP_CONTENT" > "$_ASP_FILE"
}

# Prune old audit sessions, keeping only the most recent N.
# Also enforces total size limit.
# Usage: audit_prune "$CWD" 10
audit_prune() {
  _APR_CWD="$1"
  _APR_MAX="${2:-$AUDIT_MAX_SESSIONS}"
  _APR_AUDIT_DIR="$_APR_CWD/.rtl-agent-team/audit"

  [ ! -d "$_APR_AUDIT_DIR" ] && return 0

  # List session directories sorted by mtime (oldest first)
  # Exclude session-id.txt and other non-directory entries
  _APR_COUNT=0
  _APR_DIRS=""
  for _apr_d in "$_APR_AUDIT_DIR"/*/; do
    [ -d "$_apr_d" ] || continue
    _APR_COUNT=$((_APR_COUNT + 1))
    _APR_DIRS="$_APR_DIRS
$_apr_d"
  done

  # Remove excess sessions (oldest first)
  if [ "$_APR_COUNT" -gt "$_APR_MAX" ]; then
    _APR_REMOVE=$((_APR_COUNT - _APR_MAX))
    # Sort by mtime ascending — use ls -1td for reverse chronological, then tail
    _APR_SORTED=$(ls -1td "$_APR_AUDIT_DIR"/*/ 2>/dev/null | tail -n "$_APR_REMOVE")
    for _apr_old in $_APR_SORTED; do
      [ -d "$_apr_old" ] && rm -rf "$_apr_old"
    done
  fi

  # Enforce total size limit (approximate, using du)
  _APR_SIZE_KB=$(du -sk "$_APR_AUDIT_DIR" 2>/dev/null | cut -f1)
  _APR_MAX_KB=$((AUDIT_MAX_SIZE_MB * 1024))
  if [ -n "$_APR_SIZE_KB" ] && [ "$_APR_SIZE_KB" -gt "$_APR_MAX_KB" ] 2>/dev/null; then
    # Remove oldest sessions until under limit
    for _apr_old in $(ls -1td "$_APR_AUDIT_DIR"/*/ 2>/dev/null | tail -n +2); do
      [ -d "$_apr_old" ] || continue
      rm -rf "$_apr_old"
      _APR_SIZE_KB=$(du -sk "$_APR_AUDIT_DIR" 2>/dev/null | cut -f1)
      [ -z "$_APR_SIZE_KB" ] && break
      [ "$_APR_SIZE_KB" -le "$_APR_MAX_KB" ] 2>/dev/null && break
    done
  fi
}
