#!/bin/sh
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

SRC_BLOCK=$(mktemp)
OUT_FILE=$(mktemp)
trap 'rm -f "$SRC_BLOCK" "$OUT_FILE"' EXIT

awk -v start="$SRC_START" -v end="$SRC_END" '
  $0 == start {in_block = 1; next}
  $0 == end {in_block = 0; exit}
  in_block {print}
' "$SKILL_FILE" > "$SRC_BLOCK"

if [ ! -s "$SRC_BLOCK" ]; then
  echo "error: no hook export block found in $SKILL_FILE" >&2
  exit 1
fi

awk -v start="$DST_START" -v end="$DST_END" -v block="$SRC_BLOCK" '
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
