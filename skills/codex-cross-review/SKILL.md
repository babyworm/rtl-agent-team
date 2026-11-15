---
name: codex-cross-review
description: "One Codex review as an independent second reviewer. Reports open disagreements. At phase boundaries or on 'codex review'."
user-invocable: true
argument-hint: "[phase number | 'auto']"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, AskUserQuestion
---

<Purpose>
Ask Codex once, as an independent second reviewer. Report disagreements. A further exchange runs only when the user asks.
</Purpose>

<Use_When>
- Phase boundary: before declaring any phase (1-6) complete
- Manual invocation: user wants independent cross-review of current work
- Quality gate: need a second opinion from a different model family
</Use_When>

<Do_Not_Use_When>
- Codex CLI is not installed (check with `codex --version`)
- Work is still in progress (cross-review should happen on completed deliverables)
- Phase 7 exploration (exempt from pipeline gates)
</Do_Not_Use_When>

## Prerequisites

1. **Codex CLI installed**: `codex --version` must succeed
2. **OpenAI API key configured**: Codex must be authenticated
3. **Phase artifacts exist**: the phase being reviewed must have produced deliverables

## Configuration

The skill reads `~/.codex/config.toml` for model and effort settings.
Users configure their preferred model and reasoning effort there — the skill never overrides these.

Display the current config to the user at the start of every invocation:
```
Codex Config: model={model}, reasoning_effort={effort}
```

## Execution

### Phase Auto-Detection
If no phase number is provided, detect the current phase from:
1. Most recently modified `docs/phase-N-*/` directory
2. Ask user if ambiguous

### Spawn Cross-Reviewer Agent

```
Task(subagent_type="rtl-agent-team:codex-cross-reviewer",
     prompt="Run cross-review for Phase {N}.
             Phase intent: {brief description from phase docs}.
             Target artifacts: {list of docs/code paths}.
             Changed files: {from git diff}.")
```

## Integration Protocol (for Phase Orchestrators)

Phase orchestrators (P1-P6) should invoke cross-review as their **penultimate step**
(before declaring phase complete):

```
# In orchestrator agent prompt, before final step:
Step N-1: Cross-Review Gate
  Task(subagent_type="rtl-agent-team:codex-cross-reviewer",
       prompt="Cross-review Phase {N}. Artifacts: {paths}.")
  # MANDATORY explicit verdict check:
  Read(".rat/cross-review/phase-{N}/cross-review-report.md")
  # Verdict is CONSENSUS, or USER_DECIDED after the user answers the open items.
  # If neither, do not declare the phase complete.
```

Orchestrators that integrate cross-review:
- `p1-research-orchestrator` — review spec analysis quality
- `p2-arch-orchestrator` — review architecture decisions + ref model
- `p3-uarch-orchestrator` — review uArch design + BFM
- `p4-implement-orchestrator` — review RTL implementation
- `p4-rtl-sanity-orchestrator` — review rapid implementation
- `p5-verify-orchestrator` — review verification completeness
- `p6-review-orchestrator` — review design note quality

## One Exchange

```
Claude writes the phase summary → Codex reviews once → findings JSON
No open disputes and APPROVE → CONSENSUS
Open disputes → ask the user once → USER_DECIDED
```

Do not run a second Codex pass to confirm the same verdict.

## Artifacts

Cross-review artifacts are phase-scoped for traceability:
- `.rat/cross-review/review-schema.json` — shared JSON schema
- `.rat/cross-review/phase-{N}/phase-summary.md` — phase context sent to Codex
- `.rat/cross-review/phase-{N}/prompt-round-1.txt` — the one prompt sent to Codex
- `.rat/cross-review/phase-{N}/round-1.json` — Codex's response
- `.rat/cross-review/phase-{N}/resolution-state.json` — running resolution tracker
- `.rat/cross-review/phase-{N}/cross-review-report.md` — final summary report
- `.rat/cross-review/phase-{N}/escalation-summary.md` — generated if user escalation needed

Completion marker: `.rat/state/cross-review-phase-${N}-done` (e.g., `cross-review-phase-2-done`)
