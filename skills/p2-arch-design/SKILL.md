---
name: p2-arch-design
description: "Phase 2 architecture design: HW feasibility of P1 candidates, block datapaths, reference C model. Use for 'architecture design', 'Phase 2', 'block design'."
user-invocable: true
argument-hint: "[--resume | architecture-focus]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute Phase 2 architecture design pipeline. Reviews Phase 1 algorithm candidates
for HW feasibility, designs block-level architecture with data paths, builds
reference C model in parallel, and iterates with dynamic-convergence review (min 2, max 5 rounds).
</Purpose>

<Use_When>
- Phase 1 research is complete and architecture design is needed
- User says "architecture design", "Phase 2", "block design"
- Need HW feasibility evaluation of algorithm candidates
</Use_When>

<Do_Not_Use_When>
- Phase 1 research is not complete (run p1-spec-research first)
- Only need architecture review of existing docs (use arch-review)
- Need DSE with multiple architecture candidates (use rat-dse)
</Do_Not_Use_When>

## Prerequisites

Phase 1 completion required:
- `docs/phase-1-research/iron-requirements.json` must exist
- `docs/phase-1-research/open-requirements.json` (optional — absent if P1 had no open items)
- `docs/phase-1-research/io_definition.json` must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p1-spec-research`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

If $ARGUMENTS contains "--resume":

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Resume Phase 2 architecture design from existing artifacts in
     docs/phase-2-architecture/ and reviews/phase-2-architecture/. $ARGUMENTS")

Else:

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Execute Phase 2 architecture design. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages P1 candidate HW review, parallel architecture
design + ref model, dynamic-convergence iterative review, and artifact finalization.

## Workflow Notes

- Open Resolution: resolve all OPEN-1-* items from Phase 1 `open-requirements.json`
- Compliance Check: verify REQ-A-* architecture requirements against P1 iron requirements
- Exit gate includes `compliance-pass` — architecture must not contradict any iron requirement
