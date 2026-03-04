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

# Check if the file is an RTL file
case "$FILE_PATH" in
  *.sv|*.svh|*.v|*.vh)
    STATE_DIR="$CWD/.rtl-agent-team/state"
    mkdir -p "$STATE_DIR"
    TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"

    # Add file if not already tracked (locked for concurrent access)
    if acquire_lock "$TRACK_FILE"; then
      if ! grep -qxF "$FILE_PATH" "$TRACK_FILE" 2>/dev/null; then
        printf '%s\n' "$FILE_PATH" >> "$TRACK_FILE"
      fi
      release_lock "$TRACK_FILE"
    fi

    # Count tracked files
    COUNT=$(wc -l < "$TRACK_FILE" 2>/dev/null | tr -d ' ')
    BASENAME=$(basename "$FILE_PATH")

    # Phase 6 stale detection: if a completed Phase 6 review exists, mark it stale
    P6_MSG=""
    P6_REVIEW_DIR="$CWD/reviews/phase-6-review"
    if [ -d "$P6_REVIEW_DIR" ] && ls "$P6_REVIEW_DIR"/*.md 2>/dev/null | grep -q .; then
      touch "$STATE_DIR/phase6-stale"
      P6_MSG=" Phase 6 리뷰 문서가 stale 상태로 표시되었습니다 — 검증 완료 후 코드 리뷰/디자인 노트도 갱신하세요."
    fi

    # Escape JSON-special characters in path/message variables
    SAFE_BASENAME=$(jsonu_escape "$BASENAME")
    SAFE_STATE_DIR=$(jsonu_escape "$STATE_DIR")
    printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[RTL Verify Gate] %s 수정됨 (미검증 RTL 파일 %s개). RTL 수정 완료 후 반드시: (1) TB 생성/업데이트, (2) cocotb/verilator 기능 시뮬레이션 수행. lint만으로는 기능 정확성을 보장할 수 없습니다. 완료 시: touch %s/rtl-verify-done%s"}}' "$SAFE_BASENAME" "$COUNT" "$SAFE_STATE_DIR" "$P6_MSG"
    ;;
  *)
    # Not an RTL file, no action needed
    printf '{"continue":true}'
    ;;
esac
