#!/bin/sh
# RTL Skill Activation Hook: PreToolUse:Skill
# Auto-creates completion state when an rtl-agent-team skill is invoked.
# Reads completion criteria from .rtl-agent-team/skill-completion-criteria.json.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

json_escape() {
  jsonu_escape "$1"
}

emit_continue() {
  MSG="$1"
  if [ -n "$MSG" ]; then
    printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"%s"}}' "$(json_escape "$MSG")"
  else
    printf '{"continue":true}'
  fi
  exit 0
}

# Extract skill name from tool input
SKILL_NAME=$(jsonu_get_input_string "$INPUT" "skill")

# Only handle rtl-agent-team skills
case "$SKILL_NAME" in
  rtl-agent-team:*)
    SHORT_NAME="${SKILL_NAME#rtl-agent-team:}"
    ;;
  *)
    emit_continue ""
    ;;
esac

SETUP_EXTRA_CONTEXT=""
if [ "$SHORT_NAME" = "rtl-setup" ]; then
  BOOTSTRAP_SCRIPT="$PLUGIN_ROOT/skills/rtl-setup/scripts/install_project_templates.sh"
  if [ -x "$BOOTSTRAP_SCRIPT" ]; then
    BOOTSTRAP_OUTPUT=$("$BOOTSTRAP_SCRIPT" "$CWD" 2>&1)
    BOOTSTRAP_STATUS=$?
    if [ "$BOOTSTRAP_STATUS" -eq 0 ]; then
      BOOTSTRAP_SUMMARY=$(printf '%s\n' "$BOOTSTRAP_OUTPUT" | tail -n 1)
      if [ -n "$BOOTSTRAP_SUMMARY" ]; then
        SETUP_EXTRA_CONTEXT="[rtl-setup bootstrap] $BOOTSTRAP_SUMMARY"
      else
        SETUP_EXTRA_CONTEXT="[rtl-setup bootstrap] template script installation completed."
      fi
    else
      SETUP_EXTRA_CONTEXT="[rtl-setup bootstrap] template installation failed: $BOOTSTRAP_OUTPUT"
    fi
  else
    SETUP_EXTRA_CONTEXT="[rtl-setup bootstrap] installer not found: $BOOTSTRAP_SCRIPT"
  fi
fi

# Setup prerequisite check — exempt categories:
# Category 1 — Self-reference: rtl-setup (cannot check setup before setup)
# Category 2 — Passive policies: *-policy (14 skills, loaded by agents via skills: field, not user-invocable)
# Category 3 — File-extension conventions: systemverilog, systemverilog-assertion, systemc, uvm
# Category 4 — Reference-only: rtl-orchestrate (routing table, no execution)
case "$SHORT_NAME" in
  rtl-setup|*-policy|systemverilog|systemverilog-assertion|systemc|uvm|rtl-orchestrate)
    ;;
  *)
    if [ ! -f "$CWD/.claude/rules/rtl-coding-conventions.md" ]; then
      printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[SETUP REQUIRED] rtl-setup has not been run. Project rules (.claude/rules/), guides, and directory structure are missing — the pipeline may not function correctly. Run /rtl-agent-team:rtl-setup first."}}'
      exit 0
    fi
    ;;
esac

STATE_DIR="$CWD/.rtl-agent-team/state"
SKILL_STATE="$STATE_DIR/skill-active.json"
CRITERIA_FILE="$PLUGIN_ROOT/.rtl-agent-team/skill-completion-criteria.json"

# Team mode: worker sessions skip skill state management (leader only)
TEAM_CONFIG="$STATE_DIR/team-config.json"
if [ -n "${CLAUDE_SESSION_ID:-}" ] && [ -f "$TEAM_CONFIG" ]; then
  . "$SCRIPT_DIR/lib/json-util.sh" 2>/dev/null
  TEAM_MODE=$(jsonu_get_file_path_bool "$TEAM_CONFIG" "team_mode")
  if [ "$TEAM_MODE" = "true" ]; then
    LEADER_ID=$(jsonu_get_file_path_string "$TEAM_CONFIG" "leader_session_id")
    if [ -n "$LEADER_ID" ] && [ "$CLAUDE_SESSION_ID" != "$LEADER_ID" ]; then
      emit_continue "$SETUP_EXTRA_CONTEXT"
    fi
  fi
fi

# Don't override if already active (re-invocation within same session)
if [ -f "$SKILL_STATE" ]; then
  emit_continue "$SETUP_EXTRA_CONTEXT"
fi

# Read criteria for this skill from config
if [ ! -f "$CRITERIA_FILE" ]; then
  emit_continue "$SETUP_EXTRA_CONTEXT"
fi

# Extract criteria for this skill using grep+sed (no jq dependency)
CRITERIA=$(sed -n "s/.*\"${SHORT_NAME}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$CRITERIA_FILE")

if [ -z "$CRITERIA" ]; then
  # No criteria defined for this skill, allow without loop
  emit_continue "$SETUP_EXTRA_CONTEXT"
fi

# Create state file
mkdir -p "$STATE_DIR"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)
cat > "$SKILL_STATE.tmp" << SKILLEOF
{
  "skill": "${SHORT_NAME}",
  "active": true,
  "iteration": 1,
  "max_iterations": 5,
  "use_escalation_ladder": true,
  "strategy": "primary",
  "dynamic_prompt": "",
  "pending": "${CRITERIA}",
  "all_complete": false,
  "started_at": "${TIMESTAMP}"
}
SKILLEOF
mv "$SKILL_STATE.tmp" "$SKILL_STATE"

printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[RTL Skill Completion Loop ACTIVATED] Skill %s has started. Completion criteria: %s. The session will not terminate until all criteria are met. When complete, set all_complete to true in .rtl-agent-team/state/skill-active.json."}}' "$SHORT_NAME" "$CRITERIA"
