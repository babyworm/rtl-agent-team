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

_extract_ctx() {
  case "$JSONU_PARSER_MODE" in
    jq)
      printf '%s' "$1" | jq -r '.hookSpecificOutput.additionalContext // empty | strings' 2>/dev/null
      ;;
    python)
      printf '%s' "$1" | "$JSONU_PY_BIN" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
v = (d.get("hookSpecificOutput") or {}).get("additionalContext") if isinstance(d, dict) else None
if isinstance(v, str):
    sys.stdout.write(v)
' 2>/dev/null
      ;;
    *)
      printf '%s' "$1" | sed -n 's/.*"additionalContext"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
      ;;
  esac
}

ACTIVATION=$(printf '%s' "$INPUT" | sh "$SCRIPT_DIR/rtl-skill-activation.sh")
PRE_CTX=$(_extract_ctx "$PREFLIGHT")
ACT_CTX=$(_extract_ctx "$ACTIVATION")
if [ -n "$PRE_CTX" ] && [ -n "$ACT_CTX" ]; then
  emit_post_context "$PRE_CTX $ACT_CTX"
elif [ -n "$PRE_CTX" ]; then
  emit_post_context "$PRE_CTX"
fi
printf '%s' "$ACTIVATION"
