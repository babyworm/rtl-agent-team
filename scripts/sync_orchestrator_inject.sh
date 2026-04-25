#!/bin/sh
# Sync the SessionStart routing markdown from skills/rtl-orchestrate/SKILL.md
# into hooks/rtl-orchestrator-inject.sh as a JSON-encoded envelope.
#
# Why this exists:
# Claude Code's SessionStart hook validator requires JSON output with a
# `hookSpecificOutput.hookEventName` field. Raw markdown stdout fails schema
# validation. To keep the runtime hook dependency-free (no jq/python at session
# start) we encode the markdown into JSON here at sync time and embed the
# resulting single line inside a `cat << 'JSON_EOF'` heredoc. The heredoc is
# single-quoted, so all bytes are preserved literally — no runtime escaping.
#
# Output schema (after sync):
#   # BEGIN GENERATED ROUTING BLOCK - sync via scripts/sync_orchestrator_inject.sh
#   cat << 'JSON_EOF'
#   {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}
#   JSON_EOF
#   # END GENERATED ROUTING BLOCK
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SKILL_FILE="$ROOT_DIR/skills/rtl-orchestrate/SKILL.md"
HOOK_FILE="$ROOT_DIR/hooks/rtl-orchestrator-inject.sh"

SRC_START='<!-- SESSIONSTART_HOOK_EXPORT_START -->'
SRC_END='<!-- SESSIONSTART_HOOK_EXPORT_END -->'
DST_START='# BEGIN GENERATED ROUTING BLOCK - sync via scripts/sync_orchestrator_inject.sh'
DST_END='# END GENERATED ROUTING BLOCK'

if [ ! -f "$SKILL_FILE" ]; then
  echo "error: missing $SKILL_FILE" >&2
  exit 1
fi

if [ ! -f "$HOOK_FILE" ]; then
  echo "error: missing $HOOK_FILE" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found in PATH (required for JSON encoding)" >&2
  exit 1
fi

SRC_BLOCK=$(mktemp)
NEW_BLOCK=$(mktemp)
OUT_FILE=$(mktemp)
trap 'rm -f "$SRC_BLOCK" "$NEW_BLOCK" "$OUT_FILE"' EXIT

# 1) Extract markdown export block from SKILL.md
awk -v start="$SRC_START" -v end="$SRC_END" '
  $0 == start {in_block = 1; next}
  $0 == end {in_block = 0; exit}
  in_block {print}
' "$SKILL_FILE" > "$SRC_BLOCK"

if [ ! -s "$SRC_BLOCK" ]; then
  echo "error: no hook export block found in $SKILL_FILE" >&2
  exit 1
fi

# 2) Encode markdown into a single-line JSON envelope.
#    ensure_ascii=False preserves μ, →, etc. (UTF-8 is JSON-spec compliant).
JSON_LINE=$(python3 - "$SRC_BLOCK" << 'PYEOF'
import json, sys
src = sys.argv[1]
with open(src, "r", encoding="utf-8") as f:
    content = f.read()
out = {
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": content,
    }
}
sys.stdout.write(json.dumps(out, ensure_ascii=False))
PYEOF
)

if [ -z "$JSON_LINE" ]; then
  echo "error: python3 JSON encoding produced empty output" >&2
  exit 1
fi

# Sanity-check: the encoded line must be valid JSON before we splice it in.
printf '%s' "$JSON_LINE" | python3 -c 'import json,sys; json.loads(sys.stdin.read())' \
  || { echo "error: encoded JSON failed self-validation" >&2; exit 1; }

# 3) Build the new hook block: pre-encoded JSON inside a single-quoted heredoc.
{
  printf "cat << 'JSON_EOF'\n"
  printf '%s\n' "$JSON_LINE"
  printf 'JSON_EOF\n'
} > "$NEW_BLOCK"

# 4) Splice the new block between BEGIN/END markers in the hook file.
awk -v start="$DST_START" -v end="$DST_END" -v block="$NEW_BLOCK" '
  BEGIN {
    while ((getline line < block) > 0) {
      lines[++n] = line
    }
    close(block)
    in_dst = 0
    replaced = 0
  }

  $0 == start {
    print
    for (i = 1; i <= n; i++) {
      print lines[i]
    }
    in_dst = 1
    replaced = 1
    next
  }

  $0 == end {
    in_dst = 0
    print
    next
  }

  !in_dst {print}

  END {
    if (!replaced) {
      exit 2
    }
  }
' "$HOOK_FILE" > "$OUT_FILE" || {
  code=$?
  if [ "$code" -eq 2 ]; then
    echo "error: destination markers not found in $HOOK_FILE" >&2
  fi
  exit "$code"
}

mv "$OUT_FILE" "$HOOK_FILE"
echo "synced: $HOOK_FILE (JSON envelope, $(printf '%s' "$JSON_LINE" | wc -c | tr -d ' ') bytes)"
