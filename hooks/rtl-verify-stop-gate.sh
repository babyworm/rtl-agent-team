#!/bin/sh
# RTL Verify Stop Gate: blocks session exit if RTL files were modified without verification.
#
# Tracking file: .rtl-agent-team/state/rtl-modified-files.txt (one path per line)
# Verification evidence: .rtl-agent-team/state/rtl-verify-done (marker file)
# Waiver: .rtl-agent-team/state/rtl-verify-waiver (bypass marker)
#
# If modified RTL files exist and no evidence/waiver is found, session exit is BLOCKED.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
VERIFY_DONE="$STATE_DIR/rtl-verify-done"
VERIFY_WAIVER="$STATE_DIR/rtl-verify-waiver"

if teamu_should_skip_gate "$STATE_DIR"; then
  printf '{"continue":true}'
  exit 0
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
FILES=$(jsonu_escape "$FILES")

printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[RTL Verify Gate BLOCKED] %s개 RTL 파일이 수정되었지만 기능 검증이 수행되지 않았습니다: %s. 다음 중 하나를 수행하세요: (1) /rtl-agent-team:rtl-p5s-func-verify 실행하여 기능 검증 수행, (2) 검증 불필요 시 touch .rtl-agent-team/state/rtl-verify-waiver, (3) 수정 추적 초기화: rm .rtl-agent-team/state/rtl-modified-files.txt"}}' "$COUNT" "$FILES"
