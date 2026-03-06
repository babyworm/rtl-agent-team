# Structured Output Annotations (Audit Protocol)

Annotate key moments with RAT (Reasoning Audit Tag) markers for traceable decision records.

## Tag Format

```
[RAT: CATEGORY | SOURCE] Description
```

## Categories

| Category | Purpose | Source Label Required |
|----------|---------|---------------------|
| THOUGHT | Reasoning step, hypothesis, analysis | No |
| DECISION | Choice made between alternatives | Yes (mandatory) |
| INSIGHT | Non-obvious discovery or finding | No |
| DELEGATE | Delegating work to another agent | No |
| WARNING | Risk, concern, or potential issue | No |

## Decision Source Labels (DECISION tags only)

| Label | Meaning |
|-------|---------|
| USER_CONFIRMED | User explicitly confirmed this choice |
| SPEC_DERIVED | Traceable to specification clause (cite section) |
| AGENT_ASSUMED | Agent inference (must include justification) |

## Examples

```
[RAT: DECISION | USER_CONFIRMED] Selected H.264 High Profile per user target constraints.
[RAT: DECISION | SPEC_DERIVED] FIFO depth=16 per Section 4.2 (REQ-0042).
[RAT: DECISION | AGENT_ASSUMED] 2-stage deblocking pipeline (1.3x throughput margin).
[RAT: DELEGATE] Spawning power-analyzer for dynamic power estimation.
[RAT: WARNING] CDC at DPB interface — no synchronizer detected.
[RAT: THOUGHT] Evaluating async FIFO vs dual-clock SRAM for cross-domain transfer.
[RAT: INSIGHT] Transform skip mode eliminates 40% of multiplications for QP>32.
```

## Usage Rules

1. Every DECISION tag MUST include a source label
2. AGENT_ASSUMED decisions MUST include brief justification
3. DELEGATE tags should name the target agent
4. WARNING tags should be specific and actionable
5. Use tags at natural decision points — do not over-annotate routine operations

## Prompt Self-Report

On spawn, save your received task description to:
```
.rtl-agent-team/audit/{session_id}/prompts/{NNN}_{agent-name}.md
```
where `{session_id}` is read from `.rtl-agent-team/audit/session-id.txt`
and `{NNN}` is a zero-padded sequence number.

If the session directory does not exist, skip prompt self-report silently.
