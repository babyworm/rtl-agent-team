#!/bin/sh
# RTL Phase State Bootstrap Hook: PreToolUse:Skill
# Initializes phase state files for new P4/P5A/P5B action skills.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/spawn-context-util.sh"

jsonu_detect_parser

emit_continue() {
  MSG="$1"
  if [ -n "$MSG" ]; then
    printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"%s"}}' "$(jsonu_escape "$MSG")"
  else
    printf '{"continue":true}'
  fi
  exit 0
}

emit_block() {
  MSG="$1"
  printf '{"continue":false,"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$(jsonu_escape "$MSG")"
  exit 0
}

get_file_mtime_epoch() {
  TARGET_FILE="$1"
  if [ ! -e "$TARGET_FILE" ]; then
    printf ''
    return 0
  fi
  stat -c %Y "$TARGET_FILE" 2>/dev/null \
    || stat -f %m "$TARGET_FILE" 2>/dev/null \
    || printf ''
}

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

SKILL_NAME=$(jsonu_get_input_string "$INPUT" "skill")
case "$SKILL_NAME" in
  rtl-agent-team:*)
    SHORT_NAME="${SKILL_NAME#rtl-agent-team:}"
    ;;
  *)
    emit_continue ""
    ;;
esac

SETUP_HINT=""
if [ "$JSONU_PARSER_MODE" = "sed" ]; then
  SETUP_HINT="[ENV WARNING] No jq/python JSON parser available — running in fallback (sed) mode. For stability, run /rtl-agent-team:rat-setup and ensure jq or python3 is available."
fi

# Write spawn context manifest for agent context handoff.
SCTX_MSG=""
sctx_write_manifest "$CWD" "$SHORT_NAME"
SCTX_RC=$?
if [ "$SCTX_RC" -eq 0 ]; then
  SCTX_MSG=$(sctx_summary "$CWD")
fi
if [ -n "$SCTX_MSG" ]; then
  if [ -n "$SETUP_HINT" ]; then
    SETUP_HINT="$SETUP_HINT $SCTX_MSG"
  else
    SETUP_HINT="$SCTX_MSG"
  fi
fi

# Skip bootstrap if project setup marker is absent.
if [ ! -f "$CWD/.claude/rules/rtl-coding-conventions.md" ]; then
  emit_continue "$SETUP_HINT"
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
    P5A_STATE="$CWD/.rtl-agent-team/state/p5a-state.json"
    if [ ! -f "$P5A_STATE" ]; then
      MSG="[P5B Gate BLOCKED] P5A functional closure state file (.rtl-agent-team/state/p5a-state.json) not found. Run /rtl-agent-team:rtl-p5a-functional-closure first."
      if [ -n "$SETUP_HINT" ]; then
        MSG="$MSG $SETUP_HINT"
      fi
      emit_block "$MSG"
    fi

    P5A_VERDICT=$(jsonu_get_file_path_string "$P5A_STATE" "gates.p5a_exit.verdict")
    if [ "$P5A_VERDICT" != "pass" ]; then
      [ -z "$P5A_VERDICT" ] && P5A_VERDICT="unknown"
      MSG="[P5B Gate BLOCKED] P5A handoff insufficient: gates.p5a_exit.verdict=$P5A_VERDICT. Complete P5A with PASS verdict before running P5B."
      if [ -n "$SETUP_HINT" ]; then
        MSG="$MSG $SETUP_HINT"
      fi
      emit_block "$MSG"
    fi

    # Staleness guard: if tracked RTL files were modified after P5A PASS, re-run P5A.
    # Aggregate all tracking files: global + session-specific (team mode) + fallback
    _P5B_STATE_DIR="$CWD/.rtl-agent-team/state"
    _P5B_COMBINED=$(cat "$_P5B_STATE_DIR"/rtl-modified-files*.txt 2>/dev/null | sort -u)
    P5A_MTIME=$(get_file_mtime_epoch "$P5A_STATE")
    if [ -n "$P5A_MTIME" ] && [ -n "$_P5B_COMBINED" ]; then
      LATEST_RTL_MTIME=""
      while IFS= read -r TRACKED_PATH; do
        [ -z "$TRACKED_PATH" ] && continue
        case "$TRACKED_PATH" in
          /*) RTL_FILE="$TRACKED_PATH" ;;
          *) RTL_FILE="$CWD/$TRACKED_PATH" ;;
        esac
        [ -f "$RTL_FILE" ] || continue
        RTL_MTIME=$(get_file_mtime_epoch "$RTL_FILE")
        [ -z "$RTL_MTIME" ] && continue

        if [ -z "$LATEST_RTL_MTIME" ] || [ "$RTL_MTIME" -gt "$LATEST_RTL_MTIME" ]; then
          LATEST_RTL_MTIME="$RTL_MTIME"
        fi
      done <<_P5B_TRACK_EOF
$_P5B_COMBINED
_P5B_TRACK_EOF

      if [ -n "$LATEST_RTL_MTIME" ] && [ "$LATEST_RTL_MTIME" -gt "$P5A_MTIME" ]; then
        MSG="[P5B Gate BLOCKED] RTL changes detected after P5A PASS (stale functional closure). Re-run /rtl-agent-team:rtl-p5a-functional-closure to refresh functional closure."
        if [ -n "$SETUP_HINT" ]; then
          MSG="$MSG $SETUP_HINT"
        fi
        emit_block "$MSG"
      fi
    fi

    TEMPLATE="$PLUGIN_ROOT/skills/rtl-silicon-validation-policy/templates/p5b-state.json"
    TARGET="$CWD/.rtl-agent-team/state/p5b-state.json"
    ;;
  *)
    emit_continue "$SETUP_HINT"
    ;;
esac

# Resume-friendly: never overwrite existing state.
if [ -f "$TARGET" ]; then
  emit_continue "$SETUP_HINT"
fi

if [ ! -f "$TEMPLATE" ]; then
  emit_continue "$SETUP_HINT"
fi

mkdir -p "$(dirname "$TARGET")"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)
sed "s/{{TIMESTAMP}}/${TIMESTAMP}/g" "$TEMPLATE" > "$TARGET.tmp"
mv "$TARGET.tmp" "$TARGET"

emit_continue "$SETUP_HINT"
