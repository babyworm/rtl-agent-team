#!/bin/sh
# Reduced parsing cannot safely recover all paths and nested decision flags.
INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser
CWD=$(jsonu_get_root_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
if [ "$JSONU_PARSER_MODE" = sed ] && rat_is_project "$CWD"; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[RAT] Install jq or select Python >=3.9 through RAT_PYTHON. The sed fallback cannot reliably enforce hooks for escaped paths or nested decision flags."}}'
else
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}'
fi
