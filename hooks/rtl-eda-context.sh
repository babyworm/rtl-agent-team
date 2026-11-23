#!/bin/sh
# Tell the session where EDA settings come from without copying site data into its transcript.
input=$(cat)
script_dir=$(cd "$(dirname "$0")" && pwd)
. "$script_dir/lib/json-util.sh"
. "$script_dir/lib/posix-util.sh"
jsonu_detect_parser
event=$(jsonu_get_root_string "$input" hook_event_name)
case "$event" in SessionStart|SubagentStart) ;; *) exit 0 ;; esac

# Settings live in the plugin data folder. Bash commands never receive
# CLAUDE_PLUGIN_DATA, so hand them the same folder as RAT_DATA_DIR.
data=${RAT_DATA_DIR:-${CLAUDE_PLUGIN_DATA:-}}
if [ "$event" = SessionStart ] && [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
  printf 'export RAT_DATA_DIR=%s\n' "$(shq "$CLAUDE_PLUGIN_DATA")" >> "$CLAUDE_ENV_FILE"
fi

if [ -d "${RAT_PROJECT_ROOT:-}" ]; then
  root=$RAT_PROJECT_ROOT
elif [ -d "${CLAUDE_PROJECT_DIR:-}" ]; then
  root=$CLAUDE_PROJECT_DIR
else
  root=$(jsonu_get_root_string "$input" cwd)
  root=${root:-$PWD}
  if [ ! -f "$root/rat_config.json" ]; then
    git_root=$(git -C "$root" rev-parse --show-toplevel 2>/dev/null) && root=$git_root
  fi
fi

if [ -f "$root/rat_config.json" ]; then
  source_hint='the project rat_config.json'
elif [ -n "$data" ] && [ -f "$data/env-config.json" ]; then
  source_hint='the user env-config.json and its default_site profile when selected'
else
  printf '{"hookSpecificOutput":{"hookEventName":"%s"}}\n' "$event"
  exit 0
fi
printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"[RAT EDA] For EDA work use %s. Read effective settings with bundled scripts/eda_runner.py get --root <project-root> --key <key> (e.g. preferences.simulator). Assign a distinct RAT_EXPERIMENT_ID to each parallel experiment. A remote run that prints Results: experiment/<id>/ keeps its outputs there at their usual relative paths: read them from that folder, and reuse one RAT_EXPERIMENT_ID for steps that share outputs (compile then run, regression then coverage merge)."}}\n' "$event" "$source_hint"
