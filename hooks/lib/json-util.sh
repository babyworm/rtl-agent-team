#!/bin/sh
# Shared JSON helper utilities for hooks.
# Supports parser preference: jq -> python3/python -> sed fallback.

jsonu_escape() {
  # Escape JSON-special characters and control bytes (U+0000–U+001F).
  # Tiered: jq (full) → python (full) → sed+tr (best-effort fallback).
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$1" | jq -Rs '.' 2>/dev/null | sed 's/^"//; s/"$//' | tr -d '\n'
  elif [ -n "${JSONU_PY_BIN:-}" ]; then
    printf '%s' "$1" | "$JSONU_PY_BIN" -c 'import json,sys; s=sys.stdin.read(); print(json.dumps(s)[1:-1], end="")' 2>/dev/null
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g' | tr '\001-\037' '[ *]'
  fi
}

# Same rules as rat_select_python (hooks/lib/python-util.sh), which callers of this file
# may not have sourced: the plugin floor, and never macOS's install-dialog stub.
jsonu_python_ok() {
  _JP_PATH=$(command -v "$1" 2>/dev/null) || return 1
  if [ "$_JP_PATH" -ef /usr/bin/python3 ] && [ "$(uname -s 2>/dev/null)" = Darwin ]; then
    _JP_DEV=$(xcode-select -p 2>/dev/null) && [ -x "$_JP_DEV/usr/bin/python3" ] || return 1
  fi
  "$_JP_PATH" -c 'import sys; sys.exit(sys.version_info < (3,9))' >/dev/null 2>&1
}

# Prints the checked path, so later calls run the interpreter that passed the check.
jsonu_python() {
  if [ -n "${RAT_PYTHON:-}" ]; then
    jsonu_python_ok "$RAT_PYTHON" || return 1
    printf '%s' "$_JP_PATH"
    return 0
  fi
  for _JP_BIN in python3 python python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
    jsonu_python_ok "$_JP_BIN" || continue
    printf '%s' "$_JP_PATH"
    return 0
  done
  return 1
}

jsonu_detect_parser() {
  JSONU_PARSER_MODE='sed'
  JSONU_PY_BIN=""
  # Probe Python only when it can matter: no jq, or the Python parser forced. With jq this
  # saves an interpreter start on every hook call.
  if ! command -v jq >/dev/null 2>&1 || [ "${RTL_FORCE_PYTHON_PARSER:-0}" = 1 ]; then
    JSONU_PY_BIN=$(jsonu_python) || JSONU_PY_BIN=""
  fi
  if command -v jq >/dev/null 2>&1; then
    JSONU_PARSER_MODE=jq
  elif [ -n "$JSONU_PY_BIN" ]; then
    JSONU_PARSER_MODE=python
  fi
  if [ "${RTL_FORCE_JSON_FALLBACK:-0}" = 1 ]; then
    JSONU_PARSER_MODE='sed'
    JSONU_PY_BIN=""
  elif [ "${RTL_FORCE_PYTHON_PARSER:-0}" = 1 ] && [ -n "$JSONU_PY_BIN" ]; then
    JSONU_PARSER_MODE=python
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

# Read a tool parameter from a Claude Code hook stdin payload.
# Claude Code nests tool parameters under `.tool_input` (e.g. Edit's file_path,
# Bash's command, Skill's skill arg); session-level fields (cwd, session_id,
# hook_event_name, tool_name) sit at the root. We look inside `tool_input` FIRST,
# then fall back to the root, so legacy/flat test payloads work too. A tool
# parameter can share a session field's name, so read session fields with
# jsonu_get_root_string instead.
jsonu_get_input_string() {
  JSONU_INPUT="$1"
  JSONU_KEY="$2"

  case "$JSONU_PARSER_MODE" in
    jq)
      # Index tool_input only when it is an object; otherwise (absent or a
      # non-object) fall back to the root key. Guarding the type avoids a jq
      # error when tool_input is a scalar, matching the python branch.
      printf '%s' "$JSONU_INPUT" | jq -r --arg key "$JSONU_KEY" \
        '(if (.tool_input | type) == "object" then .tool_input[$key] else null end) // .[$key] // empty' 2>/dev/null
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
ti = payload.get("tool_input")
if isinstance(ti, dict) and isinstance(ti.get(key), str):
    sys.stdout.write(ti[key])
elif isinstance(payload.get(key), str):
    sys.stdout.write(payload[key])
' "$JSONU_KEY" 2>/dev/null
      ;;
    *)
      # Last-resort fallback when jq/python are unavailable. The whole-string
      # scan matches the key wherever it sits, so nested tool_input values are
      # already covered.
      printf '%s' "$JSONU_INPUT" | sed -n "s/.*\"$JSONU_KEY\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
      ;;
  esac
}

# Batch Python-backed state reads. Values are escaped data, never evaluated as shell.
jsonu_cache_file() {
  JSONU_CACHE_FILE=""
  [ "${JSONU_PARSER_MODE:-}" = python ] && [ -f "$1" ] || return 0
  JSONU_CACHE_DATA=$("$JSONU_PY_BIN" - "$1" <<'PYCACHE'
import json,sys
try: data=json.load(open(sys.argv[1]))
except (OSError,ValueError): data={}
def flatten(node,path):
    if isinstance(node,dict):
        for key,value in node.items(): flatten(value,path+[key])
    elif isinstance(node,(str,int,float,bool)):
        kind='bool' if isinstance(node,bool) else 'string' if isinstance(node,str) else 'num'
        if kind=='num' and (not isinstance(node,int)): return
        value=('true' if node else 'false') if kind=='bool' else str(node)
        value=value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')
        print('.'.join(path)+'\t'+kind+'\t'+value)
flatten(data,[])
PYCACHE
) || return 0
  JSONU_CACHE_FILE="$1"
}

jsonu_cached_value() {
  _JCV=$(printf '%s\n' "$JSONU_CACHE_DATA" | awk -F '\t' -v key="$1" -v kind="$2" '$1==key && $2==kind {sub(/^[^\t]*\t[^\t]*\t/,"");print;exit}')
  printf '%b' "$_JCV"
}

jsonu_get_file_path_string() {
  if [ "${JSONU_CACHE_FILE:-}" = "$1" ]; then
    jsonu_cached_value "$2" string
    return 0
  fi
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
    elif isinstance(node, (list, dict)):
        print(json.dumps(node, separators=(",", ":")))
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
  if [ "${JSONU_CACHE_FILE:-}" = "$1" ]; then
    jsonu_cached_value "$2" bool
    return 0
  fi
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
  if [ "${JSONU_CACHE_FILE:-}" = "$1" ]; then
    jsonu_cached_value "$2" num
    return 0
  fi
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

# Print a top-level string field of a hook input. Unlike jsonu_get_input_string it
# never reads tool_input, whose fields can share a name with the root's: the Agent
# tool's full input schema has a cwd of its own (the directory to run the agent in).
# The sed fallback drops everything from "tool_input" on: Claude Code writes the session
# fields first, and a field the root lacks (agent_id on the main thread) must not be
# found in tool_input or tool_response instead.
# Usage: CWD=$(jsonu_get_root_string "$INPUT" "cwd")
jsonu_get_root_string() {
  case "$JSONU_PARSER_MODE" in
    jq)
      printf '%s' "$1" | jq -r --arg key "$2" '.[$key] | strings' 2>/dev/null
      ;;
    python)
      printf '%s' "$1" | "$JSONU_PY_BIN" -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
value = payload.get(sys.argv[1]) if isinstance(payload, dict) else None
if isinstance(value, str):
    sys.stdout.write(value)
' "$2" 2>/dev/null
      ;;
    *)
      printf '%s' "$1" | tr '\n' ' ' | sed 's/"tool_input"[[:space:]]*:.*//' | \
        sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
      ;;
  esac
}

# Print the session id of a hook input: its root session_id field (never tool_input's),
# else CLAUDE_CODE_SESSION_ID (which Claude Code exports to command hooks), else the
# legacy CLAUDE_SESSION_ID. Anything but a plain token prints nothing: at most 128
# ASCII letters, digits, '.', '_' and '-'. The letters are spelled out because in a
# UTF-8 locale bash's A-Z and a-z ranges also match letters such as é.
# Usage: SID=$(jsonu_session_id "$INPUT")
jsonu_session_id() {
  _JSI=$(jsonu_get_root_string "$1" "session_id")
  [ -n "$_JSI" ] || _JSI=${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}
  case "$_JSI" in
    *[!0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._-]*) _JSI="" ;;
  esac
  [ "${#_JSI}" -le 128 ] || _JSI=""
  printf '%s' "$_JSI"
}
