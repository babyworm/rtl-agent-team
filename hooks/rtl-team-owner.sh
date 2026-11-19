#!/bin/sh
# Capture team ownership from a main-thread write, not model-authored identifiers.
INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
jsonu_detect_parser
CWD=$(jsonu_get_root_string "$INPUT" cwd)
[ -z "$CWD" ] && CWD=$(pwd)
SESSION_CWD=$CWD
RAT_DIR=$(rat_project_dir "$CWD")
[ -n "$RAT_DIR" ] || emit_post_continue
CWD=$(dirname "$RAT_DIR")
[ -z "$(jsonu_get_root_string "$INPUT" agent_id)" ] || emit_post_continue
TARGET=$(jsonu_get_input_string "$INPUT" file_path)
TARGET=$(ratu_normalize_path "$TARGET" "$SESSION_CWD" "$CWD")
[ "$TARGET" = "$(basename "$RAT_DIR")/state/team-config.json" ] || emit_post_continue
SESSION=$(jsonu_session_id "$INPUT")
[ -n "$SESSION" ] || emit_post_continue
CONFIG="$RAT_DIR/state/team-config.json"
[ -f "$CONFIG" ] || emit_post_continue
FINGERPRINT=$(cksum < "$CONFIG" | awk '{print $1 ":" $2}')
printf '{"session_id":"%s","fingerprint":"%s"}\n' "$(jsonu_escape "$SESSION")" "$FINGERPRINT" | ratu_state_write "$RAT_DIR/state/team-owner.json"
emit_post_continue
