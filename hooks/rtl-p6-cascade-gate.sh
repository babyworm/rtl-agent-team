#!/bin/sh
# RTL Phase 6 Cascade Gate: Stop hook
# Blocks session exit when RTL files were modified after Phase 6 review was completed.
#
# Stale marker:   .rtl-agent-team/state/phase6-stale       (set by rtl-edit-tracker.sh)
# Cascade done:   .rtl-agent-team/state/phase6-cascade-done (set manually after updating docs)
#
# Flow:
#   - phase6-stale absent            → allow exit (Phase 6 was never completed or no RTL edits)
#   - phase6-cascade-done present    → clean up both markers, allow exit
#   - otherwise                      → BLOCK exit, instruct to re-run lint + update review docs

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
STALE_MARKER="$STATE_DIR/phase6-stale"
CASCADE_DONE="$STATE_DIR/phase6-cascade-done"

# Team-awareness: if running inside a team and not the leader, skip this gate.
TEAM_CONFIG="$STATE_DIR/team-config.json"
if [ -f "$TEAM_CONFIG" ]; then
  _TEAM_MODE=$(sed -n 's/.*"team_mode"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' "$TEAM_CONFIG" | head -n 1)
  _LEADER_ID=$(sed -n 's/.*"leader_session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)
  if [ "$_TEAM_MODE" = "true" ]; then
    _TC_CREATED=$(sed -n 's/.*"created_at"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TEAM_CONFIG" | head -n 1)
    _TC_STALE=false
    if [ -n "$_TC_CREATED" ]; then
      _TC_START=$(date -d "$_TC_CREATED" +%s 2>/dev/null \
        || date -jf "%Y-%m-%dT%H:%M:%SZ" "$_TC_CREATED" +%s 2>/dev/null \
        || echo "")
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

# If no stale marker, Phase 6 was not affected — allow exit
if [ ! -f "$STALE_MARKER" ]; then
  printf '{"continue":true}'
  exit 0
fi

# If cascade work is confirmed done, clean up and allow exit
if [ -f "$CASCADE_DONE" ]; then
  rm -f "$STALE_MARKER" "$CASCADE_DONE"
  printf '{"continue":true}'
  exit 0
fi

# Phase 6 stale and cascade not yet confirmed — BLOCK exit
printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[Phase 6 Cascade Gate BLOCKED] Phase 6 review 문서가 존재하는데 RTL 파일이 수정되었습니다. 다음을 수행해야 합니다: (1) lint 재실행 (verilator --lint-only -Wall), (2) code-review.md 갱신, (3) design-note.md 갱신. 완료 시: touch .rtl-agent-team/state/phase6-cascade-done"}}'
