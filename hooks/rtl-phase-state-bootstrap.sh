#!/bin/sh
# RTL Phase State Bootstrap Hook: PreToolUse:Skill
# Initializes phase state files for new P4/P5A/P5B action skills.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

emit_continue() {
  printf '{"continue":true}'
  exit 0
}

SKILL_NAME=$(printf '%s' "$INPUT" | sed -n 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
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
