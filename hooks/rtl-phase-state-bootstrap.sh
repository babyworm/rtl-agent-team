#!/bin/sh
# Skill preflight and accepted-call state bootstrap.
# Initializes phase state files for new P4/P5A/P5B action skills.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/spawn-context-util.sh"
. "$SCRIPT_DIR/lib/posix-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
. "$SCRIPT_DIR/lib/skill-event-util.sh"

jsonu_detect_parser
HOOK_EVENT=$(jsonu_get_root_string "$INPUT" "hook_event_name")
[ -n "$HOOK_EVENT" ] || HOOK_EVENT="PreToolUse"

CWD=$(jsonu_get_root_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

SKILL_NAME=$(skillu_name "$INPUT")
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
  SETUP_HINT="[ENV WARNING] No jq/python JSON parser available — running in fallback (sed) mode. For stability, run /rtl-agent-team:rat-init-project and ensure jq or python3 is available."
fi

# P5B gate: P5B needs a fresh P5A PASS. It runs before the state writes below
# (compliance state and report, spawn-context manifest), so a call it denies
# leaves them as they were. Like the template bootstrap, it applies only once
# the project is set up.
if [ "$HOOK_EVENT" != "PostToolUse" ] && [ "$SHORT_NAME" = "rtl-p5b-silicon-validation" ] &&
   { [ -f "$CWD/.claude/rules/rtl-coding-conventions.md" ] || [ -f "$HOME/.claude/rules/rtl-coding-conventions.md" ]; }; then
  P5A_STATE="$RAT_DIR/state/p5a-state.json"
  if [ ! -f "$P5A_STATE" ]; then
    MSG="[P5B Gate BLOCKED] P5A functional closure state file ${P5A_STATE} not found. P5B needs a P5A PASS first: ask the user whether to run /rtl-agent-team:rtl-p5a-functional-closure now."
    if [ -n "$SETUP_HINT" ]; then
      MSG="$MSG $SETUP_HINT"
    fi
    emit_block "$MSG"
  fi

  # Keep the verdict as JSON so a multiline string cannot be reduced to its first line.
  P5A_VERDICT=""
  case "$JSONU_PARSER_MODE" in
    jq) P5A_VERDICT=$(jq -cs 'if length == 1 then .[0].gates.p5a_exit.verdict else null end' "$P5A_STATE" 2>/dev/null) ;;
    python) P5A_VERDICT=$("$JSONU_PY_BIN" -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1]))["gates"]["p5a_exit"]["verdict"]))' "$P5A_STATE" 2>/dev/null) ;;
  esac
  if [ "$P5A_VERDICT" != '"pass"' ]; then
    MSG="[P5B Gate BLOCKED] P5A handoff insufficient: gates.p5a_exit.verdict must be the JSON string \"pass\". P5B needs a P5A PASS."
    if [ "$P5A_VERDICT" = '"fail"' ]; then
      MSG="[P5B Gate BLOCKED] P5A handoff insufficient: gates.p5a_exit.verdict=fail. P5B needs a P5A PASS: ask the user how to proceed."
    fi
    if [ -n "$SETUP_HINT" ]; then
      MSG="$MSG $SETUP_HINT"
    fi
    emit_block "$MSG"
  fi

  # Staleness guard: if tracked RTL files were modified after P5A PASS, re-run P5A.
  # Aggregate all tracking files: global + session-specific (team mode) + fallback
  _P5B_STATE_DIR="$RAT_DIR/state"
  _P5B_COMBINED=$(cat "$_P5B_STATE_DIR"/rtl-modified-files*.txt 2>/dev/null | sort -u)
  P5A_MTIME=$(get_mtime_epoch "$P5A_STATE")
  if [ -n "$P5A_MTIME" ] && [ -n "$_P5B_COMBINED" ]; then
    LATEST_RTL_MTIME=""
    while IFS= read -r TRACKED_PATH; do
      [ -z "$TRACKED_PATH" ] && continue
      case "$TRACKED_PATH" in
        /*) RTL_FILE="$TRACKED_PATH" ;;
        *) RTL_FILE="$CWD/$TRACKED_PATH" ;;
      esac
      [ -f "$RTL_FILE" ] || continue
      RTL_MTIME=$(get_mtime_epoch "$RTL_FILE")
      [ -z "$RTL_MTIME" ] && continue

      if [ -z "$LATEST_RTL_MTIME" ] || [ "$RTL_MTIME" -gt "$LATEST_RTL_MTIME" ]; then
        LATEST_RTL_MTIME="$RTL_MTIME"
      fi
    done <<_P5B_TRACK_EOF
$_P5B_COMBINED
_P5B_TRACK_EOF

    if [ -n "$LATEST_RTL_MTIME" ] && [ "$LATEST_RTL_MTIME" -gt "$P5A_MTIME" ]; then
      MSG="[P5B Gate BLOCKED] RTL changes detected after P5A PASS (stale functional closure). Ask the user whether to re-run /rtl-agent-team:rtl-p5a-functional-closure now."
      if [ -n "$SETUP_HINT" ]; then
        MSG="$MSG $SETUP_HINT"
      fi
      emit_block "$MSG"
    fi
  fi
fi

# Loading a Skill can still be denied after PreToolUse. Do not switch the phase,
# discard its prior report, or deploy state until the Skill call has succeeded.
[ "$HOOK_EVENT" != "PreToolUse" ] || emit_continue "$SETUP_HINT"

# Compliance state bootstrap — iron requirement paths per phase
# Overwrite if phase changed (prevents stale upstream paths from prior phase)
# NOTE: Must run BEFORE sctx_write_manifest() which reads compliance-state.json
# NOTE: Gated on setup marker to preserve pre-setup behavior (no filesystem writes
#       for uninitialized projects)
if [ -f "$CWD/.claude/rules/rtl-coding-conventions.md" ] || [ -f "$HOME/.claude/rules/rtl-coding-conventions.md" ]; then
  _CS_FILE="$RAT_DIR/state/compliance-state.json"
  _cs_current_phase=""
  if [ -f "$_CS_FILE" ]; then
    _cs_current_phase=$(jsonu_get_file_path_string "$_CS_FILE" "phase")
  fi
  if [ ! -f "$_CS_FILE" ] || [ "$_cs_current_phase" != "$SHORT_NAME" ]; then
    _cs_upstream=""
    _cs_open=""
    case "$SHORT_NAME" in
      # BEGIN GENERATED PHASE_MAP
      p2-arch-design)
        _cs_upstream='["docs/phase-1-research/iron-requirements.json"]'
        _cs_open="docs/phase-1-research/open-requirements.json"
        ;;
      rtl-p3-uarch-design)
        _cs_upstream='["docs/phase-1-research/iron-requirements.json","docs/phase-2-architecture/iron-requirements.json"]'
        _cs_open="docs/phase-2-architecture/open-requirements.json"
        ;;
      rtl-p4-implement|rtl-p4-rapid-impl|rtl-p4-block-parallel|rat-p4p5-impl-verify|rtl-p5-verify|rtl-p5a-functional-closure|rtl-p5b-silicon-validation|rtl-p6-design-review)
        _cs_upstream='["docs/phase-1-research/iron-requirements.json","docs/phase-2-architecture/iron-requirements.json","docs/phase-3-uarch/iron-requirements.json"]'
        _cs_open=""
        ;;
      # END GENERATED PHASE_MAP
    esac

    if [ -n "$_cs_upstream" ]; then
      mkdir -p "$RAT_DIR/state"
      cat > "$_CS_FILE" << _CS_EOF
{
  "phase": "$SHORT_NAME",
  "upstream_iron_paths": $_cs_upstream,
  "open_requirements_path": "$_cs_open"
}
_CS_EOF
      # New phase: invalidate any prior-phase compliance-report.json so the
      # completion gate cannot auto-satisfy compliance-pass from an upstream run.
      rm -f "$RAT_DIR/state/compliance-report.json" 2>/dev/null || true
    fi
  elif [ -f "$_CS_FILE" ]; then
    # Same-phase re-invocation: content is still correct. Refresh the marker
    # mtime AND drop any prior-run compliance-report.json outright, so THIS run
    # must produce a fresh report rather than reusing the last run's PASS.
    # (Deleting the report — not just comparing mtimes — avoids the same-second
    # boundary where a prior report and the touched marker share a timestamp.)
    touch "$_CS_FILE" 2>/dev/null || true
    rm -f "$RAT_DIR/state/compliance-report.json" 2>/dev/null || true
  fi
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

# Skip remaining bootstrap (template copying) if project setup marker is absent.
if [ ! -f "$CWD/.claude/rules/rtl-coding-conventions.md" ] && [ ! -f "$HOME/.claude/rules/rtl-coding-conventions.md" ]; then
  emit_continue "$SETUP_HINT"
fi

TEMPLATE=""
TARGET=""
case "$SHORT_NAME" in
  rtl-p4-rapid-impl)
    TEMPLATE="$PLUGIN_ROOT/skills/rtl-p4-rapid-impl-policy/templates/p4-state.json"
    TARGET="$RAT_DIR/state/p4-state.json"
    ;;
  rtl-p5a-functional-closure)
    TEMPLATE="$PLUGIN_ROOT/skills/rtl-p5a-functional-closure-policy/templates/p5a-state.json"
    TARGET="$RAT_DIR/state/p5a-state.json"
    ;;
  rtl-p5b-silicon-validation)
    TEMPLATE="$PLUGIN_ROOT/skills/rtl-silicon-validation-policy/templates/p5b-state.json"
    TARGET="$RAT_DIR/state/p5b-state.json"
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
