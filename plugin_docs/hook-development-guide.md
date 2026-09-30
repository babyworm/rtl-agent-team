# Hook Development Guide

## Overview

Hooks are event-driven shell scripts that enforce quality gates, track state, and inject
context into Claude Code sessions. They execute automatically on specific events (session
start, tool use, session stop) without requiring user invocation.

All 14 hooks are registered in `hooks/hooks.json` and run by the Claude Code plugin runtime.

## POSIX sh Constraint

Hook scripts are invoked with `sh`, **not** `bash`. This is a Claude Code plugin runtime
requirement — the plugin calls `sh "${CLAUDE_PLUGIN_ROOT}/hooks/script.sh"`.

Practical rules:
- Use `[` not `[[` for conditionals
- No bash arrays, `${var,,}`, `<<<`, process substitution, or `local -n`
- Use `$(cmd)` not backticks
- Prefix internal variables with `_` to avoid namespace collisions (e.g., `_CR_VERDICT`)
- Scripts in `scripts/` may use bash (specified via shebang), but `hooks/*.sh` must not

## hooks.json Structure

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolName|OtherTool",
        "hooks": [
          {
            "type": "command",
            "command": "sh \"${CLAUDE_PLUGIN_ROOT}/hooks/script.sh\"",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

**Event types**: `SessionStart`, `PreToolUse`, `PostToolUse`, `SubagentStart`, `SubagentStop`, `Stop`

**Matcher**: For `PreToolUse`/`PostToolUse`, matches the tool name (e.g., `Edit|Write|Bash`,
`Skill`, `Agent`). Use `*` for all-tool matching (SessionStart, Stop, Subagent events).

**Timeout**: Seconds before the hook is killed. Default 3s for responsiveness.

## Hook Input/Output Protocol

### Input
Hooks receive JSON on **stdin** containing event-specific fields. Common fields:
- `cwd` — current working directory of the user session
- `skill` — skill name (PreToolUse:Skill and PostToolUse:Skill)
- `file_path` — edited file path (PostToolUse:Edit/Write)
- `subagent_type` — agent type (SubagentStart/Stop)

Standard preamble to read and parse input:
```sh
INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
jsonu_detect_parser
CWD=$(jsonu_get_root_string "$INPUT" "cwd")
```

### Output

**PreToolUse/PostToolUse hooks** — emit JSON to stdout:
```sh
# Allow with context injection
printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"msg"}}'

# Deny one tool call; Claude receives the reason (emit_block)
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"msg"}}'
```

**Stop hooks** — emit JSON to stdout:
```sh
# Allow session exit
printf '{"continue":true}'

# Keep Claude working; Claude receives the reason (emit_stop_block, via stopu_gate)
printf '{"decision":"block","reason":"msg"}'

# Let Claude stop and show the user a message (emit_stop_notice)
printf '{"systemMessage":"msg"}'
```

Never emit `"continue": false` from a gate: Claude Code gives it precedence over
`decision` and `permissionDecision`, ends the turn, and drops the reason (verified
live on CLI 2.1.282; `tests/unit/test_hook_output_contract.py` enforces it).
Stop gates block through `stopu_gate` (`hooks/lib/stop-budget-util.sh`). It lets
Claude stop with a notice to the user in two cases:
- after `RAT_STOP_BLOCK_LIMIT` blocks (default 3) without progress in one
  continuation chain;
- from the chain's seventh Stop on, whichever hooks blocked the earlier Stops. This
  keeps RAT gates inside Claude Code's cap of 8 consecutive blocked Stops.

After its notice a gate stays silent for the rest of the chain.

To use it:
- Set `STOP_CHAIN=$(stopu_chain_active "$INPUT" <state-dir> <gate-ids>)` on every
  Stop, right after the team-mode skip and before any other exit. The call counts the
  chain's Stops, so a gate that skips a Stop undercounts. A gate that missed the
  chain start (its budget was written for another `prompt_id`) hands over.
- Pass progress text that changes when the gate's condition moves.
- Call `stopu_clear` where the gate is satisfied.

Stages whose next step is a user decision call `stopu_gate <id> … "$MSG" "$MSG" 0`.
Limit 0 gives the notice once per chain; a direct `emit_stop_notice` would repeat
it on every chained Stop. A gate that keeps its own attempt counter, like the
skill completion ladder, asks `stopu_decision` first, so it counts only the Stops
it blocks.

Hooks resolve the project with `rat_project_dir "$CWD"` and then use
`CWD=$(dirname "$RAT_DIR")` for project paths. `rat_project_dir` walks up to
`$CLAUDE_PROJECT_DIR`, because Claude Code reports the session's current directory
as the hook `cwd` and a `cd` persists. Hooks identify the session with
`jsonu_session_id "$INPUT"`: the input's `session_id`, else `CLAUDE_CODE_SESSION_ID`.
Claude Code never sets `CLAUDE_SESSION_ID`.

**SessionStart hooks** — emit a valid JSON envelope when stdout is non-empty. Put
injected context in `hookSpecificOutput.additionalContext`; raw text is rejected by
Claude Code's hook validator:

```sh
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"msg"}}'
# No context to inject:
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}'
```

### When to Use emit_continue/emit_block

The helpers in `hooks/lib/hook-output-util.sh` standardize PreToolUse/PostToolUse output:
- `emit_continue "message"` — allow the tool call, inject `additionalContext`
- `emit_continue ""` — allow silently (no context injection)
- `emit_block "reason"` — deny the tool call with a reason
- `emit_post_context "message"` — PostToolUse: give Claude context after the tool ran (`hookEventName` `PostToolUse`)

Stop hooks do **not** use these helpers, because Stop hooks block session exit rather than tool calls. They block and notify only through `stopu_gate` (see Output above), which calls `emit_stop_block` or `emit_stop_notice`, and allow the stop with `emit_post_continue`.

## Shared Libraries (`hooks/lib/`)

| File | Purpose |
|------|---------|
| `json-util.sh` | JSON parsing with jq/python/sed fallback chain. `jsonu_detect_parser()`, `jsonu_get_input_string()`, `jsonu_get_root_string()`, `jsonu_session_id()`, `jsonu_get_file_path_string()`, `jsonu_get_file_path_bool()`, `jsonu_get_file_path_num()`, `jsonu_escape()` |
| `flock-util.sh` | POSIX mkdir-based file locking. `acquire_lock()`, `release_lock()`. Stale lock detection via PID and age |
| `hook-output-util.sh` | `emit_continue()`, `emit_block()`, `emit_post_context()`, `emit_post_continue()` for PreToolUse/PostToolUse JSON output; `emit_stop_block()`, `emit_stop_notice()` for Stop gates, called through `stopu_gate` |
| `team-gate-util.sh` | `teamu_should_skip_gate()` — bypass stop gates for worker/coordinator sessions in team mode; `teamu_config_is_stale()` — a config not written for 2 hours is no team mode |
| `posix-util.sh` | `get_mtime_epoch()` — portable file mtime across GNU/BSD stat |
| `spawn-context-util.sh` | Spawn context manifest writer for Agent spawns |
| `audit-util.sh` | Audit session init, trace append, prompt save, prune |
| `artifact-map.sh` | Phase-to-artifact path mapping |
| `compliance-gate-util.sh` | `compliance_preprocess()` — compliance-pass auto-resolution for skill completion gate |
| `rat-dir-util.sh` | `rat_project_dir()`, `rat_is_project()` — find the project's `.rat` directory, walking up to `$CLAUDE_PROJECT_DIR` |
| `stop-budget-util.sh` | No-progress breaker for Stop gates. `stopu_chain_active()`, `stopu_gate()`, `stopu_decision()`, `stopu_clear()` |

## Testing Workflow

Tests live in `tests/unit/test_hooks.py` (and `test_audit.py` for audit hooks).

Use `run_hook()` from `tests/conftest.py` to execute hooks with JSON input:
```python
from tests.conftest import HOOKS_DIR, run_hook

HOOK = HOOKS_DIR / "rtl-skill-completion-gate.sh"
result = run_hook(HOOK, {"cwd": str(tmp_project)})
assert result["continue"] is True
```

`run_hook()` runs `sh <hook>` with JSON on stdin, parses stdout as JSON.
Use the `tmp_project` fixture (provides a temp dir with `.rat/state/`).
Use the `env=` parameter to inject environment variables (e.g., `CLAUDE_PROJECT_DIR`). Pass a session id as `session_id` in the hook input, as Claude Code does.

Run tests:
```bash
python3 -m pytest tests/unit/test_hooks.py -x -q
python3 -m pytest tests/unit/test_audit.py -x -q
```

## Checklist: Adding a New Hook

1. **Create the script** in `hooks/` with `#!/bin/sh` shebang
2. **Source required libs** (`json-util.sh`, `flock-util.sh`, etc.) using `$SCRIPT_DIR/lib/`
3. **Parse input** via `INPUT=$(cat)` and `jsonu_*` functions
4. **Emit valid JSON** output matching the event type protocol
5. **Register in `hooks/hooks.json`** under the correct event and matcher
6. **Keep execution under 3 seconds** (timeout constraint)
7. **Use `_` prefix** for internal variables to avoid namespace collisions
8. **Add tests** in `tests/unit/test_hooks.py` using `run_hook()` from conftest
9. **Update routing** if the hook affects skill/agent behavior:
   - Update `skills/rtl-orchestrate/SKILL.md` (routing SSOT)
   - Run `sh scripts/sync_orchestrator_inject.sh` to regenerate hook injection
10. **Update CLAUDE.md** hook table if adding a new hook file
