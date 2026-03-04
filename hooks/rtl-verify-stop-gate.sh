#!/bin/sh
# RTL Verify Stop Gate: blocks session exit if RTL files were modified without verification.
#
# Tracking file: .rtl-agent-team/state/rtl-modified-files.txt (one path per line)
# Verification evidence: .rtl-agent-team/state/rtl-verify-done (marker file)
# Waiver: .rtl-agent-team/state/rtl-verify-waiver (bypass marker)
#
# If modified RTL files exist and no evidence/waiver is found, session exit is BLOCKED.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
VERIFY_DONE="$STATE_DIR/rtl-verify-done"
VERIFY_WAIVER="$STATE_DIR/rtl-verify-waiver"

# Team-awareness: if running inside a team and not the leader, skip this gate.
TEAM_CONFIG="$STATE_DIR/team-config.json"
if [ -f "$TEAM_CONFIG" ]; then
  _TEAM_MODE=$(sed -n 's/.*"team_mode"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' "$TEAM_CONFIG" | head -n 1)
  _LEADER_ID=$(sed -n 's/.*"leader_session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)
  if [ "$_TEAM_MODE" = "true" ]; then
    _TC_CREATED=$(sed -n 's/.*"created_at"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)
    _TC_STALE=false
    if [ -n "$_TC_CREATED" ]; then
      _TC_START=$(date -d "$_TC_CREATED" +%s 2>/dev/null || echo "")
      _TC_NOW=$(date +%s 2>/dev/null || echo "")
      if [ -n "$_TC_START" ] && [ -n "$_TC_NOW" ]; then
        if [ $(( _TC_NOW - _TC_START )) -gt 7200 ]; then
          rm -f "$TEAM_CONFIG"
          _TC_STALE=true
        fi
      fi
    fi
    if [ "$_TC_STALE" = "false" ]; then
      if [ -z "$_LEADER_ID" ] || [ "$_LEADER_ID" != "${CLAUDE_SESSION_ID:-}" ]; then
        printf '{"continue":true}'
        exit 0
      fi
    fi
  fi
fi

# If no tracked files, allow exit
if [ ! -f "$TRACK_FILE" ] || [ ! -s "$TRACK_FILE" ]; then
  printf '{"continue":true}'
  exit 0
fi

# If verification was done or waived, clean up and allow exit
if [ -f "$VERIFY_DONE" ] || [ -f "$VERIFY_WAIVER" ]; then
  rm -f "$TRACK_FILE" "$VERIFY_DONE" "$VERIFY_WAIVER"
  printf '{"continue":true}'
  exit 0
fi

# Modified RTL files exist without verification — BLOCK exit
COUNT=$(wc -l < "$TRACK_FILE" | tr -d ' ')
FILES=$(while IFS= read -r f; do basename "$f"; done < "$TRACK_FILE" | tr '\n' ', ' | sed 's/,$//')
# Escape JSON-special characters in filenames
FILES=$(printf '%s' "$FILES" | sed 's/\\/\\\\/g; s/"/\\"/g')

printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[RTL Verify Gate BLOCKED] %s개 RTL 파일이 수정되었지만 기능 검증이 수행되지 않았습니다: %s. 다음 중 하나를 수행하세요: (1) /rtl-agent-team:rtl-p5s-func-verify 실행하여 기능 검증 수행, (2) 검증 불필요 시 touch .rtl-agent-team/state/rtl-verify-waiver, (3) 수정 추적 초기화: rm .rtl-agent-team/state/rtl-modified-files.txt"}}' "$COUNT" "$FILES"
