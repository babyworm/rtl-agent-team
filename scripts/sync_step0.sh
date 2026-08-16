#!/bin/bash
# sync_step0.sh — Synchronize canonical Step 0 Context Bootstrap consumer blocks.
#
# Replaces the common Step 0 core (from "## Step 0: Context Bootstrap" or
# "### Step 0: Context Bootstrap" to the fallback close line) with the canonical
# template. Preserves any phase-specific subsections (e.g., "### Upstream Artifact
# Scan") that follow the core.
#
# Usage:
#   bash scripts/sync_step0.sh [--dry-run]
#
# Options:
#   --dry-run   Show which files would change without modifying them.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENTS_DIR="$REPO_ROOT/agents"
TEMPLATE="$REPO_ROOT/plugin_docs/agent-lib/step0-template.md"

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: Template not found: $TEMPLATE" >&2
  exit 1
fi

# Read template content (strip trailing newline for clean insertion)
TEMPLATE_CONTENT=$(cat "$TEMPLATE")

CHANGED=0
UNCHANGED=0
SKIPPED=0
TOTAL=0

for agent_file in "$AGENTS_DIR"/*.md; do
  # Skip files that do not consume the canonical Step 0 heading.
  [ ! -f "$agent_file" ] && continue
  # Match both ## and ### heading levels for Step 0
  grep -qE "^#{2,3} Step 0: Context Bootstrap" "$agent_file" || continue

  TOTAL=$((TOTAL + 1))
  BASENAME=$(basename "$agent_file")

  # Detect the heading level used for Step 0 in this file (## or ###)
  HEADING_PREFIX=$(grep -E "^#{2,3} Step 0: Context Bootstrap" "$agent_file" | head -1 | grep -oE "^#{2,3}")
  # Build the template with the correct heading level
  if [ "$HEADING_PREFIX" = "###" ]; then
    FILE_TEMPLATE=$(printf '%s' "$TEMPLATE_CONTENT" | sed '1s/^## /### /')
  else
    FILE_TEMPLATE="$TEMPLATE_CONTENT"
  fi

  # Use awk to extract and replace the Step 0 core block.
  # Core block: from "Step 0:" up to (and including) the fallback close line.
  # The fallback close line is: "If NOT found →" ... "proceeding."
  # Everything after that (### subsections) until the next "## Step" is preserved.
  RESULT=$(awk '
    BEGIN { in_step0 = 0; core_done = 0; printed_template = 0 }

    # Detect Step 0 start (## or ### heading)
    /^#{2,3} Step 0: Context Bootstrap/ {
      in_step0 = 1
      core_done = 0
      printed_template = 0
      next
    }

    # Inside Step 0 core: skip lines until we hit the fallback close
    in_step0 == 1 && core_done == 0 {
      # The fallback close line: full-line match to avoid false positives
      if ($0 == "If NOT found → `Skill(skill=\"rtl-agent-team:rat-init-project\")`. Wait for completion before proceeding.") {
        # Print template instead of the core
        if (printed_template == 0) {
          printed_template = 1
          # Template placeholder — replaced below
          print "___TEMPLATE_PLACEHOLDER___"
        }
        core_done = 1
        next
      }
      next
    }

    # After core is done, check for next ## Step heading to end Step 0 entirely
    in_step0 == 1 && core_done == 1 {
      if (/^#{2,3} Step [0-9]/) {
        in_step0 = 0
        print $0
        next
      }
      # Pass through phase-specific subsections (### Upstream Artifact Scan, etc.)
      print $0
      next
    }

    # Outside Step 0: pass through unchanged
    { print $0 }

    END {
      # Safety: if we entered Step 0 but never found the sentinel, signal failure
      if (in_step0 == 1 && core_done == 0) {
        print "___SENTINEL_NOT_FOUND___"
      }
    }
  ' "$agent_file")

  # Safety check: if sentinel was not found, skip this file to avoid data loss
  case "$RESULT" in
    *___SENTINEL_NOT_FOUND___*)
      echo "[SKIPPED] $BASENAME — sentinel line not found, Step 0 block may have drifted"
      SKIPPED=$((SKIPPED + 1))
      continue
      ;;
  esac

  # Safety check: if placeholder was never emitted, skip
  case "$RESULT" in
    *___TEMPLATE_PLACEHOLDER___*) : ;;
    *)
      echo "[SKIPPED] $BASENAME — template placeholder not generated (unexpected awk state)"
      SKIPPED=$((SKIPPED + 1))
      continue
      ;;
  esac

  # Replace placeholder with actual template content.
  # The template is multi-line, so it MUST be passed via the environment, not
  # via `awk -v`: POSIX/BSD awk rejects newlines in a -v assignment ("awk:
  # newline in string"). GNU awk tolerates it, so a -v here works on Linux CI
  # and fails on macOS — see CLAUDE.md rule 7.
  EXPECTED=$(printf '%s\n' "$RESULT" | RAT_STEP0_TMPL="$FILE_TEMPLATE" awk '
    /___TEMPLATE_PLACEHOLDER___/ { print ENVIRON["RAT_STEP0_TMPL"]; next }
    { print }
  ')

  CURRENT=$(cat "$agent_file")

  if [ "$EXPECTED" = "$CURRENT" ]; then
    UNCHANGED=$((UNCHANGED + 1))
  else
    CHANGED=$((CHANGED + 1))
    if [ "$DRY_RUN" = "true" ]; then
      echo "[WOULD CHANGE] $BASENAME"
      # Show a brief diff summary
      diff <(printf '%s\n' "$CURRENT") <(printf '%s\n' "$EXPECTED") | head -20 || true
      echo "..."
    else
      printf '%s\n' "$EXPECTED" > "$agent_file"
      echo "[UPDATED] $BASENAME"
    fi
  fi
done

echo ""
echo "Step 0 sync complete: consumer files scanned: $TOTAL, changed: $CHANGED, unchanged: $UNCHANGED, skipped: $SKIPPED."
if [ "$DRY_RUN" = "true" ] && [ "$CHANGED" -gt 0 ]; then
  echo "(dry-run mode — no files were modified)"
fi
if [ "$SKIPPED" -gt 0 ]; then
  echo "WARNING: $SKIPPED file(s) skipped due to missing sentinel. Review manually."
  exit 1
fi
