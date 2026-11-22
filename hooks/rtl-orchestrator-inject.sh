#!/bin/sh
# SessionStart hook: RTL project orchestration rules injection
# Fires when the project carries a RAT marker (.rat/ or legacy .rtl-agent-team/).
# Injects critical design rules, delegation guidance, and pipeline context.
#
# WHY THIS EXISTS:
# Plugin CLAUDE.md is NOT loaded in user projects — only skills, agents, hooks,
# and MCP servers are loaded from plugins. This hook replaces CLAUDE.md's function
# by auto-injecting the routing rules and pipeline rules that Claude needs to
# correctly orchestrate RTL design tasks.
#
# OUTPUT FORMAT:
# Claude Code's SessionStart hook validator requires JSON output with a
# `hookSpecificOutput.hookEventName` field. The routing markdown is delivered
# inside `hookSpecificOutput.additionalContext`. hooks/lib/session_inject.py reads
# the export block of skills/rtl-orchestrate/SKILL.md (the SSOT) when the session
# starts and encodes it, so there is no generated copy to keep in sync. Without
# Python >= RAT_PYTHON_MIN the envelope stays valid and one notice names the fix.

# Consume stdin (hook protocol)
INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/python-util.sh"
jsonu_detect_parser
CWD=$(jsonu_get_root_string "$INPUT" cwd)
[ -z "$CWD" ] && CWD="$(pwd)"

# RAT project marker: .rat/ (current) or .rtl-agent-team/ (legacy v0.8.11-).
# These directories are created by rtl-agent-team skills (including
# rat-init-project) when first invoked. Their presence means the project
# has actively used rtl-agent-team at least once. Generic directory names
# like rtl/ or docs/ are NOT used as markers — too many false positives.
# rat_is_project finds the marker by the rule every RAT hook uses
# (hooks/lib/rat-dir-util.sh), including the RAT_PROJECT_ROOT override.
#
# When no marker is present, emit minimal valid SessionStart JSON and exit
# silently. Per-skill init advisory (when a user invokes a rtl-agent-team
# skill in an unmarked project) is handled by rtl-skill-activation.sh.
if ! rat_is_project "$CWD"; then
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}'
  exit 0
fi

if PYTHON=$(rat_select_python 2>/dev/null); then
  if ENVELOPE=$("$PYTHON" -I "$SCRIPT_DIR/lib/session_inject.py" 2>/dev/null) && [ -n "$ENVELOPE" ]; then
    printf '%s\n' "$ENVELOPE"
    exit 0
  fi
  REASON="hooks/lib/session_inject.py could not read the routing block"
else
  REASON="the plugin needs Python >= $RAT_PYTHON_MIN for its hooks"
fi
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart"},"systemMessage":"rtl-agent-team: the project rules were not loaded because %s. Run /rtl-agent-team:rat-doctor."}\n' "$REASON"
exit 0
