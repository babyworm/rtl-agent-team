#!/bin/sh
# Shared JSON helper utilities for hooks.
# Supports parser preference: jq -> python3/python -> sed fallback.

jsonu_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g' | tr '\n' ' ' | tr '\r' ' '
}

jsonu_detect_parser() {
  JSONU_PARSER_MODE="sed"
  JSONU_PY_BIN=""

  if command -v jq >/dev/null 2>&1; then
    JSONU_PARSER_MODE="jq"
  elif command -v python3 >/dev/null 2>&1; then
    JSONU_PARSER_MODE="python"
    JSONU_PY_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    JSONU_PARSER_MODE="python"
    JSONU_PY_BIN="python"
  fi

  # Test/debug override: force legacy fallback parser path.
  if [ "${RTL_FORCE_JSON_FALLBACK:-0}" = "1" ]; then
    JSONU_PARSER_MODE="sed"
    JSONU_PY_BIN=""
  fi
}

jsonu_path_to_jq_query() {
  JSONU_PATH="$1"
  JSONU_QUERY=''
  while :; do
    JSONU_SEGMENT=${JSONU_PATH%%.*}
    JSONU_QUERY="$JSONU_QUERY.\"$JSONU_SEGMENT\""
    if [ "$JSONU_PATH" = "$JSONU_SEGMENT" ]; then
      break
    fi
    JSONU_PATH=${JSONU_PATH#*.}
  done
  printf '%s' "$JSONU_QUERY"
}

jsonu_get_input_string() {
  JSONU_INPUT="$1"
  JSONU_KEY="$2"

  case "$JSONU_PARSER_MODE" in
    jq)
      printf '%s' "$JSONU_INPUT" | jq -r --arg key "$JSONU_KEY" '.[$key] // empty' 2>/dev/null
      ;;
    python)
      printf '%s' "$JSONU_INPUT" | "$JSONU_PY_BIN" -c '
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
' "$JSONU_KEY" 2>/dev/null
      ;;
    *)
      # Last-resort fallback when jq/python are unavailable.
      printf '%s' "$JSONU_INPUT" | sed -n "s/.*\"$JSONU_KEY\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
      ;;
  esac
}

jsonu_get_file_path_string() {
  JSONU_FILE="$1"
  JSONU_KEY_PATH="$2"

  if [ ! -f "$JSONU_FILE" ]; then
    printf ''
    return 0
  fi

  case "$JSONU_PARSER_MODE" in
    jq)
      JSONU_JQ_QUERY=$(jsonu_path_to_jq_query "$JSONU_KEY_PATH")
      jq -r "($JSONU_JQ_QUERY) as \$v | if \$v == null then \"\" else (\$v|tostring) end" "$JSONU_FILE" 2>/dev/null | head -n 1
      ;;
    python)
      "$JSONU_PY_BIN" - "$JSONU_FILE" "$JSONU_KEY_PATH" 2>/dev/null <<'PY'
import json
import sys

state_file = sys.argv[1]
path = sys.argv[2].split(".")

try:
    with open(state_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            print("")
            raise SystemExit(0)
        node = node[key]
    if node is None:
        print("")
    elif isinstance(node, bool):
        print("true" if node else "false")
    else:
        print(str(node))
except Exception:
    print("")
PY
      ;;
    *)
      # Last-resort fallback when jq/python are unavailable.
      # Fail-closed for nested paths: sed can only reliably handle single-level keys.
      case "$JSONU_KEY_PATH" in
        *.*)
          printf ''
          return 0
          ;;
      esac
      JSONU_LEAF_KEY=${JSONU_KEY_PATH##*.}
      sed -n "s/.*\"$JSONU_LEAF_KEY\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$JSONU_FILE" | head -n 1
      ;;
  esac
}

jsonu_get_file_path_bool() {
  JSONU_FILE="$1"
  JSONU_KEY_PATH="$2"

  if [ ! -f "$JSONU_FILE" ]; then
    printf ''
    return 0
  fi

  case "$JSONU_PARSER_MODE" in
    jq)
      JSONU_JQ_QUERY=$(jsonu_path_to_jq_query "$JSONU_KEY_PATH")
      jq -r "($JSONU_JQ_QUERY) as \$v | if (\$v|type)==\"boolean\" then (if \$v then \"true\" else \"false\" end) else \"\" end" "$JSONU_FILE" 2>/dev/null | head -n 1
      ;;
    python)
      "$JSONU_PY_BIN" - "$JSONU_FILE" "$JSONU_KEY_PATH" 2>/dev/null <<'PY'
import json
import sys

state_file = sys.argv[1]
path = sys.argv[2].split(".")

try:
    with open(state_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            print("")
            raise SystemExit(0)
        node = node[key]
    if isinstance(node, bool):
        print("true" if node else "false")
    else:
        print("")
except Exception:
    print("")
PY
      ;;
    *)
      # Last-resort fallback when jq/python are unavailable.
      # Fail-closed for nested paths: sed can only reliably handle single-level keys.
      case "$JSONU_KEY_PATH" in
        *.*)
          printf ''
          return 0
          ;;
      esac
      # Two-pass approach for POSIX BRE compatibility (avoids GNU sed \| extension).
      JSONU_LEAF_KEY=${JSONU_KEY_PATH##*.}
      JSONU_BOOL_VAL=$(sed -n "s/.*\"$JSONU_LEAF_KEY\"[[:space:]]*:[[:space:]]*true.*/true/p" "$JSONU_FILE" | head -n 1)
      [ -z "$JSONU_BOOL_VAL" ] && JSONU_BOOL_VAL=$(sed -n "s/.*\"$JSONU_LEAF_KEY\"[[:space:]]*:[[:space:]]*false.*/false/p" "$JSONU_FILE" | head -n 1)
      printf '%s' "$JSONU_BOOL_VAL"
      ;;
  esac
}

jsonu_get_file_path_num() {
  JSONU_FILE="$1"
  JSONU_KEY_PATH="$2"

  if [ ! -f "$JSONU_FILE" ]; then
    printf ''
    return 0
  fi

  case "$JSONU_PARSER_MODE" in
    jq)
      JSONU_JQ_QUERY=$(jsonu_path_to_jq_query "$JSONU_KEY_PATH")
      jq -r "($JSONU_JQ_QUERY // null) as \$v | if (\$v|type)==\"number\" then (if \$v == (\$v|floor) then (\$v|tostring) else \"\" end) else \"\" end" "$JSONU_FILE" 2>/dev/null | head -n 1
      ;;
    python)
      "$JSONU_PY_BIN" - "$JSONU_FILE" "$JSONU_KEY_PATH" 2>/dev/null <<'PY'
import json
import sys

state_file = sys.argv[1]
path = sys.argv[2].split(".")

try:
    with open(state_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            print("")
            raise SystemExit(0)
        node = node[key]
    if isinstance(node, bool):
        print("")
    elif isinstance(node, int):
        print(str(node))
    elif isinstance(node, float):
        if node == int(node):
            print(str(int(node)))
        else:
            print("")
    else:
        print("")
except Exception:
    print("")
PY
      ;;
    *)
      # Last-resort fallback when jq/python are unavailable.
      # Fail-closed for nested paths: sed can only reliably handle single-level keys.
      case "$JSONU_KEY_PATH" in
        *.*)
          printf ''
          return 0
          ;;
      esac
      JSONU_LEAF_KEY=${JSONU_KEY_PATH##*.}
      sed -n "s/.*\"$JSONU_LEAF_KEY\"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p" "$JSONU_FILE" | head -n 1
      ;;
  esac
}
