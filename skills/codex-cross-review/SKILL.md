---
name: codex-cross-review
description: "Cross-review with Codex CLI as 2nd reviewer. Structured finding exchange, consensus loop (max 5 rounds), user escalation. Manual or auto-invoked at phase boundaries."
user-invocable: true
argument-hint: "[phase number | 'auto']"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, AskUserQuestion
---

<Purpose>
Run a structured cross-review dialogue between Claude and Codex CLI.
Codex acts as an independent 2nd reviewer. Both models exchange findings,
fixes, and rebuttals until consensus or user escalation.
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
2. `.rtl-agent-team/state/current-phase` if it exists
3. Ask user if ambiguous

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
  Read(".rtl-agent-team/cross-review/phase-{N}/cross-review-report.md")
  # Parse verdict field — must be CONSENSUS or USER_DECIDED
  # If verdict != CONSENSUS and user did not approve → do NOT proceed to completion
```

Orchestrators that integrate cross-review:
- `p1-research-orchestrator` — review spec analysis quality
- `p2-arch-orchestrator` — review architecture decisions + ref model
- `p3-uarch-orchestrator` — review uArch design + BFM
- `p4-implement-orchestrator` — review RTL implementation
- `p4-rtl-sanity-orchestrator` — review rapid implementation
- `p5-verify-orchestrator` — review verification completeness
- `p6-review-orchestrator` — review design note quality

## Review Loop Summary

```
Round 1: Claude → phase summary → Codex reviews → findings JSON
Round 2+: Claude → fixes + rebuttals → Codex re-reviews → updated findings
Consensus: verdict=APPROVE or no critical/major disputes
Max 5 rounds → AskUserQuestion escalation to user
```

## Artifacts

Cross-review artifacts are phase-scoped for traceability:
- `.rtl-agent-team/cross-review/review-schema.json` — shared JSON schema
- `.rtl-agent-team/cross-review/phase-{N}/phase-summary.md` — phase context sent to Codex
- `.rtl-agent-team/cross-review/phase-{N}/prompt-round-R.txt` — exact prompt sent each round
- `.rtl-agent-team/cross-review/phase-{N}/round-R.json` — Codex's structured response each round
- `.rtl-agent-team/cross-review/phase-{N}/resolution-state.json` — running resolution tracker
- `.rtl-agent-team/cross-review/phase-{N}/cross-review-report.md` — final summary report
- `.rtl-agent-team/cross-review/phase-{N}/escalation-summary.md` — generated if user escalation needed

Completion marker: `.rtl-agent-team/state/cross-review-phase-N-done`
