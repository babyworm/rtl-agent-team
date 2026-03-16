# P3-11: Hook Output Standardization

## Problem

40 instances of inline `printf '{"continue":true}'` across 10 hook files. Only 3 hooks
use the shared `emit_continue`/`emit_block` helpers from `hooks/lib/hook-output-util.sh`.

Two distinct JSON schemas exist:
- **PreToolUse hooks**: `{"continue":true/false, "hookSpecificOutput":{"hookEventName":"PreToolUse", ...}}`
- **Stop hooks**: `{"continue":false, "decision":"block", "reason":"..."}`

The current `emit_block()` uses the PreToolUse schema, so Stop hooks cannot use it.

## Current State

| Hook | Event | `printf` count | Uses helpers? |
|------|-------|---------------|---------------|
| `rtl-edit-tracker.sh` | PostToolUse | 11 | No |
| `rtl-audit-spawn-complete.sh` | PostToolUse | 5 | No |
| `rtl-spawn-context.sh` | PreToolUse | 4 | No |
| `rtl-skill-completion-gate.sh` | Stop | 4 | No |
| `rtl-team-progress.sh` | PostToolUse | 3 | No |
| `rtl-verify-stop-gate.sh` | Stop | 3 | No |
| `rtl-p6-cascade-gate.sh` | Stop | 3 | No |
| `stop-gate.sh` | Stop | 3 | No |
| `rtl-skill-activation.sh` | PreToolUse | 2 | No |
| `rtl-phase-state-bootstrap.sh` | PreToolUse | 0 | Yes (via emit_continue) |
| `rtl-project-init-advisor.sh` | SessionStart | 0 | Yes (via emit_continue) |
| `rtl-orchestrator-inject.sh` | SessionStart | 0 | Yes (via emit_continue) |
| `rtl-audit-init.sh` | SessionStart | 0 | No (uses own printf) |

**Total: 38 inline printf + 2 in hook-output-util.sh itself = 40**

## Solution

### Step 1: Extend hook-output-util.sh with Stop hook helpers

Add to `hooks/lib/hook-output-util.sh`:

```sh
# Emit a Stop-hook block response with reason, then exit 0.
emit_stop_block() {
  _ESB_MSG="$1"
  printf '{"continue":false,"decision":"block","reason":"%s"}' "$(jsonu_escape "$_ESB_MSG")"
  exit 0
}

# Emit a PostToolUse continue response (no additionalContext), then exit 0.
emit_post_continue() {
  printf '{"continue":true}'
  exit 0
}
```

### Step 2: Migrate each hook (mechanical replacement)

For each hook, replace inline patterns:

| Pattern | Replacement |
|---------|-------------|
| `printf '{"continue":true}'` + `exit 0` | `emit_continue ""` |
| `printf '{"continue":true}' ; exit 0` | `emit_continue ""` |
| `printf '{"continue":true,"hookSpecificOutput":...}' ; exit 0` | `emit_continue "$MSG"` |
| `printf '{"continue":false,"decision":"block","reason":"..."}' ; exit 0` | `emit_stop_block "$MSG"` |

Each hook needs to source the util:
```sh
. "$SCRIPT_DIR/lib/hook-output-util.sh"
```
(Most already source `json-util.sh` which is in the same lib dir)

### Migration Order (lowest risk first)

1. **rtl-audit-spawn-complete.sh** — 5 simple `printf+exit`, all continue
2. **rtl-team-progress.sh** — 3 simple continues
3. **rtl-skill-activation.sh** — 2 continues
4. **rtl-spawn-context.sh** — 4 continues
5. **rtl-edit-tracker.sh** — 11 continues (most instances, but all identical pattern)
6. **rtl-audit-init.sh** — 1 continue (currently own printf)
7. **stop-gate.sh** — 3 blocks (Stop hook, needs emit_stop_block)
8. **rtl-verify-stop-gate.sh** — 3 (1 block + 2 continues)
9. **rtl-p6-cascade-gate.sh** — 3 (2 blocks + 1 continue)
10. **rtl-skill-completion-gate.sh** — 4 (1 block + 3 continues)

### Step 3: Verify behavior preservation

For each migrated hook:
- Run existing tests (`python3 -m pytest tests/unit/test_hooks.py -k TestClassName`)
- Verify JSON output format is identical (regex match on test assertions)

### Step 4: Update documentation

- Update `plugin_docs/hook-development-guide.md` to mandate helpers
- Add lint rule comment in hook-output-util.sh

## Implementation Checklist

```
[ ] Add emit_stop_block() and emit_post_continue() to hook-output-util.sh
[ ] Add source line to hooks that don't already source it
[ ] Migrate rtl-audit-spawn-complete.sh (5 replacements)
[ ] Migrate rtl-team-progress.sh (3 replacements)
[ ] Migrate rtl-skill-activation.sh (2 replacements)
[ ] Migrate rtl-spawn-context.sh (4 replacements)
[ ] Migrate rtl-edit-tracker.sh (11 replacements)
[ ] Migrate rtl-audit-init.sh (1 replacement)
[ ] Migrate stop-gate.sh (3 replacements)
[ ] Migrate rtl-verify-stop-gate.sh (3 replacements)
[ ] Migrate rtl-p6-cascade-gate.sh (3 replacements)
[ ] Migrate rtl-skill-completion-gate.sh (4 replacements)
[ ] Run full test suite: 945+ passed
[ ] Update hook-development-guide.md
```

## Effort: ~2 hours | Risk: Low (mechanical, behavior-preserving)

## Rollback: Each hook migration is independent; revert individual files if needed.

## Edge Cases

- `rtl-edit-tracker.sh` has many early-exit paths with no message — use `emit_post_continue()`
- `stop-gate.sh` constructs messages with variable interpolation — extract message to variable first
- `rtl-verify-stop-gate.sh:93` has a complex printf with %s substitution — build message string, then `emit_stop_block "$MSG"`
- `rtl-p6-cascade-gate.sh:74,84` have multi-line escaped messages — use heredoc to build message variable
