#!/bin/bash
# bump-version.sh — Update version across all 6 canonical locations.
# Usage: scripts/bump-version.sh [--dry-run] <new-version>
#
# Locations updated:
#   1. package.json              "version"
#   2. .claude-plugin/plugin.json "version"
#   3. .claude-plugin/marketplace.json "metadata.version"
#   4. .claude-plugin/marketplace.json "plugins[0].version" (rtl-agent-team only)
#   5. README.md                 marketplace table version
#   6. README_kr.md              marketplace table version
#
# Does NOT touch CHANGELOG.md (manual).

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

DRY_RUN=0
NEW_VER=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -*)
      echo "error: unknown option $arg" >&2
      echo "usage: $0 [--dry-run] <new-version>" >&2
      exit 1
      ;;
    *)
      if [ -n "$NEW_VER" ]; then
        echo "error: multiple version arguments" >&2
        exit 1
      fi
      NEW_VER="$arg"
      ;;
  esac
done

if [ -z "$NEW_VER" ]; then
  echo "usage: $0 [--dry-run] <new-version>" >&2
  exit 1
fi

# Validate version format (semver-like: X.Y.Z with optional pre-release)
if ! echo "$NEW_VER" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
  echo "error: invalid version format '$NEW_VER' (expected X.Y.Z)" >&2
  exit 1
fi

# Detect current version from package.json
OLD_VER=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT_DIR/package.json" | head -1)
if [ -z "$OLD_VER" ]; then
  echo "error: cannot detect current version from package.json" >&2
  exit 1
fi

if [ "$OLD_VER" = "$NEW_VER" ]; then
  echo "error: new version ($NEW_VER) is the same as current version ($OLD_VER)" >&2
  exit 1
fi

echo "Version bump: $OLD_VER -> $NEW_VER"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "(dry-run mode — no files will be modified)"
fi
echo ""

CHANGED=0

# Helper: apply sed replacement, print diff summary
bump_file() {
  local file="$1"
  local label="$2"
  local pattern="$3"
  local replacement="$4"

  local rel_path="${file#"$ROOT_DIR"/}"

  if ! grep -q "$OLD_VER" "$file"; then
    echo "  SKIP  $rel_path ($label) — old version not found"
    return 0
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  WOULD $rel_path ($label)"
    CHANGED=$((CHANGED + 1))
    return 0
  fi

  sed -i "$pattern" "$file"
  echo "  OK    $rel_path ($label)"
  CHANGED=$((CHANGED + 1))
}

# 1. package.json "version"
bump_file "$ROOT_DIR/package.json" \
  "version field" \
  "s/\"version\"[[:space:]]*:[[:space:]]*\"$OLD_VER\"/\"version\": \"$NEW_VER\"/" \
  ""

# 2. .claude-plugin/plugin.json "version"
bump_file "$ROOT_DIR/.claude-plugin/plugin.json" \
  "version field" \
  "s/\"version\"[[:space:]]*:[[:space:]]*\"$OLD_VER\"/\"version\": \"$NEW_VER\"/" \
  ""

# 3 & 4. .claude-plugin/marketplace.json — metadata.version + plugins[0].version
# We replace only the FIRST occurrence of the old version (metadata.version),
# then the SECOND occurrence (plugins[0].version = rtl-agent-team).
# The systemverilog-lsp version is different and untouched.
MKT_FILE="$ROOT_DIR/.claude-plugin/marketplace.json"
MKT_REL="${MKT_FILE#"$ROOT_DIR"/}"
if [ "$DRY_RUN" -eq 1 ]; then
  COUNT=$(grep -c "\"$OLD_VER\"" "$MKT_FILE" || true)
  if [ "$COUNT" -ge 2 ]; then
    echo "  WOULD $MKT_REL (metadata.version)"
    echo "  WOULD $MKT_REL (plugins[0].version)"
    CHANGED=$((CHANGED + 2))
  elif [ "$COUNT" -ge 1 ]; then
    echo "  WOULD $MKT_REL (metadata.version)"
    CHANGED=$((CHANGED + 1))
  else
    echo "  SKIP  $MKT_REL — old version not found"
  fi
else
  # Replace all occurrences of the old version (metadata + first plugin).
  # The systemverilog-lsp plugin has its own version, so only OLD_VER matches are ours.
  sed -i "s/\"$OLD_VER\"/\"$NEW_VER\"/g" "$MKT_FILE"
  echo "  OK    $MKT_REL (metadata.version + plugins[0].version)"
  CHANGED=$((CHANGED + 2))
fi

# 5. README.md — marketplace table row for rtl-agent-team
bump_file "$ROOT_DIR/README.md" \
  "marketplace table" \
  "s/| $OLD_VER |$/| $NEW_VER |/" \
  ""

# 6. README_kr.md — marketplace table row for rtl-agent-team
bump_file "$ROOT_DIR/README_kr.md" \
  "marketplace table" \
  "s/| $OLD_VER |$/| $NEW_VER |/" \
  ""

echo ""

# Validate no stale references of OLD version remain in the 5 files.
# NOTE: We match both quoted (`"0.9.1"` for JSON/package.json) AND raw
# token forms (the plain-text `0.9.1` used in README marketplace tables).
# Raw-token regex uses word boundaries to avoid matching unrelated
# substrings like 0.9.10, 10.9.1, etc.
STALE_FILES=""
STALE_VER_RE='(^|[^0-9.])'"$OLD_VER"'([^0-9]|$)'
for f in \
  "$ROOT_DIR/package.json" \
  "$ROOT_DIR/.claude-plugin/plugin.json" \
  "$ROOT_DIR/.claude-plugin/marketplace.json" \
  "$ROOT_DIR/README.md" \
  "$ROOT_DIR/README_kr.md"; do
  [ "$DRY_RUN" -eq 0 ] || continue
  if grep -Eq "$STALE_VER_RE" "$f" 2>/dev/null; then
    STALE_FILES="$STALE_FILES ${f#"$ROOT_DIR"/}"
  fi
done

if [ -n "$STALE_FILES" ]; then
  echo "WARNING: stale version references ($OLD_VER) found in:$STALE_FILES"
  exit 1
fi

echo "Summary: $CHANGED location(s) updated."
if [ "$DRY_RUN" -eq 1 ]; then
  echo "Re-run without --dry-run to apply changes."
fi
