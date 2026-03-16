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
`Skill`, `TaskCreate`). Use `*` for all-tool matching (SessionStart, Stop, Subagent events).

**Timeout**: Seconds before the hook is killed. Default 3s for responsiveness.

## Hook Input/Output Protocol

### Input
Hooks receive JSON on **stdin** containing event-specific fields. Common fields:
- `cwd` — current working directory of the user session
- `skill` — skill name (PreToolUse:Skill)
- `file_path` — edited file path (PostToolUse:Edit/Write)
- `subagent_type` — agent type (SubagentStart/Stop)

Standard preamble to read and parse input:
```sh
INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
jsonu_detect_parser
CWD=$(jsonu_get_input_string "$INPUT" "cwd")
```

### Output

**PreToolUse/PostToolUse hooks** — emit JSON to stdout:
```sh
# Allow with context injection
printf '{"continue":true,"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"msg"}}'

# Block/deny a tool call
printf '{"continue":false,"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"msg"}}'
```

**Stop hooks** — emit JSON to stdout:
```sh
# Allow session exit
printf '{"continue":true}'

# Block session exit
printf '{"continue":false,"decision":"block","reason":"msg"}'
```

**SessionStart hooks** — output raw text (injected as context) or empty string.

### When to Use emit_continue/emit_block

The helpers in `hooks/lib/hook-output-util.sh` standardize PreToolUse/PostToolUse output:
- `emit_continue "message"` — allow the tool call, inject `additionalContext`
- `emit_continue ""` — allow silently (no context injection)
- `emit_block "reason"` — deny the tool call with a reason

Stop hooks do **not** use these helpers — they use the `{"continue":bool,"decision":"block","reason":"..."}` format directly, because Stop hooks block session exit rather than tool calls.

## Shared Libraries (`hooks/lib/`)

| File | Purpose |
|------|---------|
| `json-util.sh` | JSON parsing with jq/python/sed fallback chain. `jsonu_detect_parser()`, `jsonu_get_input_string()`, `jsonu_get_file_path_string()`, `jsonu_get_file_path_bool()`, `jsonu_get_file_path_num()`, `jsonu_escape()` |
| `flock-util.sh` | POSIX mkdir-based file locking. `acquire_lock()`, `release_lock()`. Stale lock detection via PID and age |
| `hook-output-util.sh` | `emit_continue()`, `emit_block()` for PreToolUse/PostToolUse JSON output |
| `team-gate-util.sh` | `teamu_should_skip_gate()` — bypass stop gates for worker/coordinator sessions in team mode |
| `posix-util.sh` | `get_mtime_epoch()` — portable file mtime across GNU/BSD stat |
| `spawn-context-util.sh` | Spawn context manifest writer for TaskCreate events |
| `audit-util.sh` | Audit session init, trace append, prompt save, prune |
| `artifact-map.sh` | Phase-to-artifact path mapping |
| `compliance-gate-util.sh` | `compliance_preprocess()` — compliance-pass auto-resolution for skill completion gate |

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
Use the `tmp_project` fixture (provides a temp dir with `.rtl-agent-team/state/`).
Use `env=` parameter to inject environment variables (e.g., `CLAUDE_SESSION_ID`).

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
