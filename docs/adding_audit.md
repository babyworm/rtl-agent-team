# Audit Logging & Decision Visualization — Design Rationale (v2)

## Purpose

This document describes the audit logging infrastructure added to RTL Agent Team.
The system captures agent spawning, skill invocation, artifact generation, and
design decision events in a structured, append-only trace log.

## Architecture

### Data Flow

```
Hook Events (SessionStart/PreToolUse/PostToolUse/Stop)
    → audit-util.sh (POSIX sh library)
    → .rtl-agent-team/audit/{session_id}/trace.jsonl
```

### Components

| Component | File | Role |
|-----------|------|------|
| Audit Utility Library | `hooks/lib/audit-util.sh` | Session init, trace append, prompt save, prune |
| Session Initializer | `hooks/rtl-audit-init.sh` | SessionStart: create audit dir, cache session ID |
| Subagent Diagnostic | `hooks/rtl-audit-subagent.sh` | SubagentStart/Stop: experimental event capture |
| Spawn Tracer | `hooks/rtl-spawn-context.sh` | PreToolUse:TaskCreate: spawn_start event |
| Spawn Complete | `hooks/rtl-audit-spawn-complete.sh` | PostToolUse:TaskCreate: spawn_complete event |
| Artifact Tracer | `hooks/rtl-edit-tracker.sh` | PostToolUse:Edit/Write: artifact_write for docs/ |
| Skill Tracer | `hooks/rtl-skill-activation.sh` | PreToolUse:Skill: skill_invoke event |
| RAT Protocol | `agents/lib/audit-output-protocol.md` | Agent structured output annotation standard |
| CLI Viewer | `scripts/show-audit.sh` | Terminal viewer with ANSI colors |
| Summary Generator | `scripts/generate-audit-summary.sh` | trace.jsonl → summary.md conversion |

### trace.jsonl Schema

```json
{
  "ts": "ISO-8601 timestamp",
  "seq": "monotonic sequence number",
  "event": "spawn_start|spawn_complete|skill_invoke|artifact_write|decision",
  "agent": "agent name",
  "parent": "parent agent (if applicable)",
  "phase": "pipeline phase number",
  "tag": "RAT tag (if applicable)",
  "source": "USER_CONFIRMED|SPEC_DERIVED|AGENT_ASSUMED",
  "detail": "human-readable description",
  "prompt_file": "path to saved prompt (if applicable)",
  "status": "started|success|failed"
}
```

### RAT (Reasoning Audit Tag) Protocol

Agents annotate key decision moments with structured tags:
- `[RAT: DECISION | SOURCE]` — choice with provenance
- `[RAT: THOUGHT]` — reasoning step
- `[RAT: DELEGATE]` — work delegation
- `[RAT: WARNING]` — risk identification
- `[RAT: INSIGHT]` — non-obvious discovery

### Session Management

- Sessions identified by `CLAUDE_SESSION_ID` or timestamp+PID fallback
- Maximum 10 sessions retained, 50MB total limit
- Automatic pruning on SessionStart

## Design Decisions

1. **Always-on**: No opt-in required. Disk managed via session pruning.
2. **POSIX sh**: Consistent with existing hook library (json-util.sh, flock-util.sh).
3. **JSONL format**: Append-only, concurrent-safe with flock, easy to parse.
4. **RAT tags in agent output**: Captured from LLM text output, not hook JSON.
5. **Prompt self-report**: Agents save their task descriptions since hook stdin
   may not include the full prompt field.
