---
name: rat-plugin-debug
description: "Plugin diagnostics: version, EDA tool status, state files, hook health. Triggers: 'rat debug', 'plugin status', troubleshooting plugin behavior."
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep
---

<Purpose>
Display RTL Agent Team plugin diagnostics for debugging and environment verification.
Shows plugin version, EDA tool availability, state file status, and hook health.
</Purpose>

<Use_When>
- Debugging plugin issues or unexpected behavior
- Verifying EDA tool installation status
- Checking plugin state files for stale or corrupt entries
- User says "debug", "diagnostics", "plugin status", "rat debug"
</Use_When>

<Do_Not_Use_When>
- Setting up a new project (use rat-init-project) or installing tools (use rat-setup)
- Running design pipeline (use rat-auto-design or phase-specific skills)
</Do_Not_Use_When>

## Execution

Run each diagnostic section and present a consolidated report. All checks are read-only and non-destructive.

### 1. Plugin Version

```bash
# Read plugin version from manifest
cat "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" 2>/dev/null | grep '"version"' | head -1
# Fallback: check if CLAUDE_PLUGIN_ROOT is set
echo "CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-NOT_SET}"
```

Report: `rtl-agent-team v{version}` and plugin root path.

### 2. EDA Tool Status

Check each tool and report version or NOT_FOUND. Group by classification:

```bash
# --- Required ---
verilator --version 2>&1 | head -1 || echo "NOT_FOUND"
python3 --version 2>&1 || echo "NOT_FOUND"
python3 -c "import cocotb; print('cocotb', cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
g++ --version 2>&1 | head -1 || echo "NOT_FOUND"
make --version 2>&1 | head -1 || echo "NOT_FOUND"
pkg-config --modversion systemc 2>/dev/null || (test -n "$SYSTEMC_HOME" && echo "systemc via SYSTEMC_HOME=$SYSTEMC_HOME") || echo "NOT_FOUND"

# --- Lint tools (at least one required) ---
verible-verilog-lint --version 2>&1 | head -1 || echo "NOT_FOUND"
slang --version 2>&1 | head -1 || echo "NOT_FOUND"

# --- Recommended ---
slang-server --version 2>&1 | head -1 || echo "NOT_FOUND"
jq --version 2>&1 || echo "NOT_FOUND"

# --- Optional ---
iverilog -V 2>&1 | head -1 || echo "NOT_FOUND"
yosys --version 2>&1 | head -1 || echo "NOT_FOUND"
sby --help 2>&1 | head -1 || echo "NOT_FOUND"
gtkwave --version 2>&1 | head -1 || echo "NOT_FOUND"
docker --version 2>&1 | head -1 || echo "NOT_FOUND"
```

Report as a table with status icons: `[OK]` installed, `[!!]` required but missing, `[--]` optional and missing.

### 3. Project Setup Status

```bash
# Check if rat-init-project has been run (marker: .claude/rules/rtl-coding-conventions.md)
test -f .claude/rules/rtl-coding-conventions.md && echo "SETUP_DONE" || echo "SETUP_NOT_DONE"

# Check directory structure
for dir in specs refc rtl sim lint syn docs reviews .rat/state; do
  test -d "$dir" && echo "[OK] $dir" || echo "[--] $dir"
done

# Check deployed rules
for f in .claude/rules/rtl-coding-conventions.md .claude/rules/rtl-verification-gate.md; do
  test -f "$f" && echo "[OK] $f" || echo "[--] $f"
done
# Diagram rules: check global CLAUDE.md tag OR local fallback file
grep -q '<markdown_diagram_rule>' ~/.claude/CLAUDE.md 2>/dev/null && echo "[OK] diagram-rules (global CLAUDE.md tag)" || \
  (test -f .claude/rules/diagram-rules.md && echo "[OK] diagram-rules (local file)" || echo "[--] diagram-rules (neither global tag nor local file)")

# Check deployed guides
for f in rtl/CLAUDE.md sim/CLAUDE.md docs/CLAUDE.md reviews/CLAUDE.md refc/CLAUDE.md syn/CLAUDE.md; do
  test -f "$f" && echo "[OK] $f" || echo "[--] $f"
done
```

### 4. State Files

```bash
# List all state files with age
find .rat/state/ -name "*.json" -type f 2>/dev/null | while read f; do
  AGE_SEC=$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0) ))
  AGE_MIN=$(( AGE_SEC / 60 ))
  SIZE=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f" 2>/dev/null || echo "?")
  echo "$f  (${SIZE}B, ${AGE_MIN}m ago)"
done

# Check for stale state (older than 2 hours)
find .rat/state/ -name "*.json" -mmin +120 -type f 2>/dev/null | while read f; do
  echo "[STALE] $f — older than 2 hours, may block hooks"
done
```

If stale files are found, suggest cleanup command:
`rm -f .rat/state/{filename}` (with user confirmation).

### 5. Hook Health

```bash
# Verify all hook scripts exist and are readable
HOOK_DIR="${CLAUDE_PLUGIN_ROOT}/hooks"
for h in stop-gate.sh rtl-verify-stop-gate.sh rtl-skill-completion-gate.sh \
         rtl-orchestrator-inject.sh rtl-edit-tracker.sh rtl-phase-state-bootstrap.sh \
         rtl-skill-activation.sh rtl-p6-cascade-gate.sh rtl-spawn-context.sh \
         rtl-team-progress.sh; do
  if [ -f "$HOOK_DIR/$h" ]; then
    echo "[OK] $h"
  else
    echo "[!!] $h — MISSING"
  fi
done

# Verify hooks.json exists
test -f "$HOOK_DIR/hooks.json" && echo "[OK] hooks.json" || echo "[!!] hooks.json — MISSING"

# Verify lib utilities
for lib in json-util.sh flock-util.sh team-gate-util.sh spawn-context-util.sh; do
  test -f "$HOOK_DIR/lib/$lib" && echo "[OK] lib/$lib" || echo "[!!] lib/$lib — MISSING"
done
```

### 6. Summary

Present a one-line verdict:
- **READY**: All required tools installed, setup done, no stale state
- **PARTIAL**: Some optional tools missing but functional
- **NOT READY**: Required tools missing or setup not done — suggest `/rat-init-project` and `/rat-setup`

```
## RAT Plugin Debug Report
- Plugin: rtl-agent-team v{version}
- EDA Tools: {X}/{Y} required OK, {A}/{B} optional OK
- Lint Gate: {verible|slang|both|NONE}
- Setup: {done|not done}
- State: {N files, M stale}
- Hooks: {all OK | N missing}
- Verdict: {READY|PARTIAL|NOT READY}
```
