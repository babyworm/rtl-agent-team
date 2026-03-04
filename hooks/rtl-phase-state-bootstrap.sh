#!/bin/sh
# RTL Phase State Bootstrap Hook: PreToolUse:Skill
# Initializes phase state files for new P4/P5A/P5B action skills.

INPUT=$(cat)

emit_continue() {
  printf '{"continue":true}'
  exit 0
}

json_get_string() {
  KEY="$1"

  # Prefer structured JSON parsing. Fallbacks keep backward compatibility.
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r --arg key "$KEY" '.[$key] // empty' 2>/dev/null
    return 0
  fi

  PY_BIN=""
  if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
  fi
  if [ -n "$PY_BIN" ]; then
    printf '%s' "$INPUT" | "$PY_BIN" -c '
import json
import sys

key = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
value = payload.get(key, "")
if isinstance(value, str):
    sys.stdout.write(value)
' "$KEY" 2>/dev/null
    return 0
  fi

  # Last-resort fallback when jq/python are unavailable.
  printf '%s' "$INPUT" | sed -n "s/.*\"$KEY\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
}

CWD=$(json_get_string "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

SKILL_NAME=$(json_get_string "skill")
case "$SKILL_NAME" in
  rtl-agent-team:*)
    SHORT_NAME="${SKILL_NAME#rtl-agent-team:}"
    ;;
  *)
    emit_continue
    ;;
esac

# Skip bootstrap if project setup marker is absent.
if [ ! -f "$CWD/.claude/rules/rtl-coding-conventions.md" ]; then
  emit_continue
fi

TEMPLATE=""
TARGET=""
case "$SHORT_NAME" in
  rtl-p4-rapid-impl)
    TEMPLATE="$PLUGIN_ROOT/skills/rtl-design-policy/templates/p4-state.json"
    TARGET="$CWD/.rtl-agent-team/state/p4-state.json"
    ;;
  rtl-p5a-functional-closure)
    TEMPLATE="$PLUGIN_ROOT/skills/rtl-functional-verify-policy/templates/p5a-state.json"
    TARGET="$CWD/.rtl-agent-team/state/p5a-state.json"
    ;;
  rtl-p5b-silicon-validation)
    TEMPLATE="$PLUGIN_ROOT/skills/rtl-silicon-validation-policy/templates/p5b-state.json"
    TARGET="$CWD/.rtl-agent-team/state/p5b-state.json"
    ;;
  *)
    emit_continue
    ;;
esac

# Resume-friendly: never overwrite existing state.
if [ -f "$TARGET" ]; then
  emit_continue
fi

if [ ! -f "$TEMPLATE" ]; then
  emit_continue
fi

mkdir -p "$(dirname "$TARGET")"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)
sed "s/{{TIMESTAMP}}/${TIMESTAMP}/g" "$TEMPLATE" > "$TARGET.tmp"
mv "$TARGET.tmp" "$TARGET"

emit_continue
