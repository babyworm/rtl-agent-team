#!/bin/sh
# Direct slash commands bypass Skill tool hooks. Run the same local preflight
# before starting completion tracking; a denied expansion creates no skill loop.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/skill-event-util.sh"
jsonu_detect_parser
HOOK_EVENT=$(jsonu_get_root_string "$INPUT" "hook_event_name")
[ "$HOOK_EVENT" = "UserPromptExpansion" ] || emit_post_continue
skillu_name "$INPUT" >/dev/null || emit_post_continue

PREFLIGHT=$(printf '%s' "$INPUT" | sh "$SCRIPT_DIR/rtl-phase-state-bootstrap.sh")
if [ "$(jsonu_get_root_string "$PREFLIGHT" "decision")" = "block" ]; then
  printf '%s' "$PREFLIGHT"
  exit 0
fi

printf '%s' "$INPUT" | sh "$SCRIPT_DIR/rtl-skill-activation.sh"
