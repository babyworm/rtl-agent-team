#!/bin/sh
# RTL Edit Tracker: PostToolUse:Edit/Write hook
# Tracks modified .sv/.svh/.v/.vh files for verification enforcement.
# When an RTL file is edited, records it in a tracking file and injects
# a reminder that functional verification (not just lint) is required.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

# Extract file_path from tool input
FILE_PATH=$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

# Check if the file is an RTL file
case "$FILE_PATH" in
  *.sv|*.svh|*.v|*.vh)
    STATE_DIR="$CWD/.rtl-agent-team/state"
    mkdir -p "$STATE_DIR"
    TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"

    # Add file if not already tracked
    if ! grep -qxF "$FILE_PATH" "$TRACK_FILE" 2>/dev/null; then
      printf '%s\n' "$FILE_PATH" >> "$TRACK_FILE"
    fi

    # Count tracked files
    COUNT=$(wc -l < "$TRACK_FILE" 2>/dev/null | tr -d ' ')
    BASENAME=$(basename "$FILE_PATH")

    printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[RTL Verify Gate] %s 수정됨 (미검증 RTL 파일 %s개). RTL 수정 완료 후 반드시: (1) TB 생성/업데이트, (2) cocotb/verilator 기능 시뮬레이션 수행. lint만으로는 기능 정확성을 보장할 수 없습니다. 완료 시: touch %s/rtl-verify-done"}}' "$BASENAME" "$COUNT" "$STATE_DIR"
    ;;
  *)
    # Not an RTL file, no action needed
    printf '{"continue":true}'
    ;;
esac
