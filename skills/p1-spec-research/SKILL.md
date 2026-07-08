---
name: p1-spec-research
description: "Phase 1 spec research: refines spec, fills gaps via user Q&A, surveys algorithm candidates with trade-offs. Use for 'research', 'spec analysis', 'Phase 1'."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute Phase 1 spec research pipeline. Refines specification, identifies gaps,
surveys candidate algorithms with trade-offs, and produces structured research
artifacts for Phase 2 architecture design.
</Purpose>

<Use_When>
- Starting a new RTL design from a specification or idea
- Need thorough spec analysis before architecture design
- User says "research", "spec analysis", "Phase 1"
- Specification has ambiguities or missing information
</Use_When>

<Do_Not_Use_When>
- Phase 1 artifacts already exist and are current
- Only need a quick domain question (use domain-consult)
- Need architecture design (use p2-arch-design — requires Phase 1 completion)
</Do_Not_Use_When>

<Phase_Workflow>
This skill runs as two stages inside the same Task() invocation:

- **Phase 0 (goal-clarifier)**: when `$ARGUMENTS` is a sparse seed, the
  orchestrator first dispatches `goal-clarifier` for an ambiguity-scored
  interview across 4 RTL dimensions (Functionality / PPA Target / Scope /
  Verification). Phase 0 writes `docs/phase-1-research/goal.md`.
- **Phase 1 (spec-analyst + research)**: spec-analyst consumes `goal.md`
  (plus any user-supplied spec document) and produces the iron/open
  requirements set as before.

When `$ARGUMENTS` points to an existing `.md`/`.txt`/`.rst` spec or is
already a rich seed (≥ 500 chars with PPA/coverage signals), Phase 0
is skipped automatically.
</Phase_Workflow>

<Assets>
| Path | Role |
|------|------|
| `scripts/score_ambiguity.py` | Pure stdlib helper for 4-dimension scoring + ambiguity %. Used by goal-clarifier each round. |
| `templates/goal.md` | Output skeleton for `docs/phase-1-research/goal.md`. |
| `references/goal-dimensions.md` | 4-dimension scoring rubric + question seeds + anti-patterns. |
</Assets>

## Prerequisites

None — this is the first phase entry point.

## Execution

Task(subagent_type="rtl-agent-team:p1-research-orchestrator",
     prompt="Execute Phase 1 spec research. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages spec refinement, solution tree exploration,
sub-domain expert coordination, and 3-round chief review.

## Output Artifacts

- `docs/phase-1-research/iron-requirements.json` — settled functional/performance requirements (REQ-F-*, REQ-P-*)
- `docs/phase-1-research/open-requirements.json` — research topics deferred to Phase 2 (OPEN-1-*)
- `docs/phase-1-research/io_definition.json` — I/O interface definitions
- Classification verification step confirms each requirement is tagged as either iron (acceptance_criteria defined) or open (research_needed).
