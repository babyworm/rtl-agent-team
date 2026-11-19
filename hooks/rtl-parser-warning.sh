#!/bin/sh
# Reduced parsing cannot safely recover all paths and nested decision flags.
cat >/dev/null
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
jsonu_detect_parser
if [ "$JSONU_PARSER_MODE" = sed ]; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[RAT] Install jq or select Python >=3.9 through RAT_PYTHON. The sed fallback cannot reliably enforce hooks for escaped paths or nested decision flags."}}'
else
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}'
fi
