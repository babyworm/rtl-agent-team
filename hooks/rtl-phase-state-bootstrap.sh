#!/bin/sh
# RTL Phase State Bootstrap Hook: PreToolUse:Skill
# Initializes phase state files for new P4/P5A/P5B action skills.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"

jsonu_detect_parser

emit_continue() {
  MSG="$1"
  if [ -n "$MSG" ]; then
    printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(jsonu_escape "$MSG")"
  else
    printf '{"continue":true}'
  fi
  exit 0
}

emit_block() {
  MSG="$1"
  printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(jsonu_escape "$MSG")"
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
  SETUP_HINT="[ENV WARNING] jq/python JSON parser가 없어 fallback(sed) 모드로 동작 중입니다. 안정성을 위해 /rtl-agent-team:rtl-setup 실행 후 jq 또는 python3 환경을 준비하세요."
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
      MSG="[P5B Gate BLOCKED] P5A functional closure 상태 파일(.rtl-agent-team/state/p5a-state.json)이 없습니다. 먼저 /rtl-agent-team:rtl-p5a-functional-closure 를 실행하세요."
      if [ -n "$SETUP_HINT" ]; then
        MSG="$MSG $SETUP_HINT"
      fi
      emit_block "$MSG"
    fi

    P5A_VERDICT=$(jsonu_get_file_path_string "$P5A_STATE" "gates.p5a_exit.verdict")
    if [ "$P5A_VERDICT" != "pass" ]; then
      [ -z "$P5A_VERDICT" ] && P5A_VERDICT="unknown"
      MSG="[P5B Gate BLOCKED] P5A handoff 불충분: gates.p5a_exit.verdict=$P5A_VERDICT. P5A를 PASS 상태로 완료한 뒤 P5B를 실행하세요."
      if [ -n "$SETUP_HINT" ]; then
        MSG="$MSG $SETUP_HINT"
      fi
      emit_block "$MSG"
    fi

    # Staleness guard: if tracked RTL files were modified after P5A PASS, re-run P5A.
    TRACK_FILE="$CWD/.rtl-agent-team/state/rtl-modified-files.txt"
    P5A_MTIME=$(get_file_mtime_epoch "$P5A_STATE")
    if [ -n "$P5A_MTIME" ] && [ -f "$TRACK_FILE" ] && [ -s "$TRACK_FILE" ]; then
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
      done < "$TRACK_FILE"

      if [ -n "$LATEST_RTL_MTIME" ] && [ "$LATEST_RTL_MTIME" -gt "$P5A_MTIME" ]; then
        MSG="[P5B Gate BLOCKED] P5A PASS 이후 RTL 변경이 감지되었습니다(stale functional closure). /rtl-agent-team:rtl-p5a-functional-closure 를 재실행해 functional closure를 갱신하세요."
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
