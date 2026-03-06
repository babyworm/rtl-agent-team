---
name: p2-arch-design
description: "Phase 2 architecture design. Reviews P1 algorithm candidates for HW implementation feasibility, designs block-level data paths, builds reference C model, and iterates with 3-round review."
user-invocable: true
argument-hint: "[--resume | architecture-focus]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 2 architecture design pipeline. Reviews Phase 1 algorithm candidates
for HW feasibility, designs block-level architecture with data paths, builds
reference C model in parallel, and iterates with 3-round review.
</Purpose>

<Use_When>
- Phase 1 research is complete and architecture design is needed
- User says "architecture design", "Phase 2", "block design"
- Need HW feasibility evaluation of algorithm candidates
</Use_When>

<Do_Not_Use_When>
- Phase 1 research is not complete (run p1-spec-research first)
- Only need architecture review of existing docs (use arch-review)
- Need DSE with multiple architecture candidates (use rtl-dse)
</Do_Not_Use_When>

## Prerequisites

Phase 1 completion required:
- `docs/phase-1-research/requirements.json` must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:p1-spec-research`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Execute Phase 2 architecture design. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages P1 candidate HW review, parallel architecture
design + ref model, 3-round iterative review, and artifact finalization.
