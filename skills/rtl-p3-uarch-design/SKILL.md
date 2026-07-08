---
name: rtl-p3-uarch-design
description: "Phase 3 uArch design: maps P2 blocks to sub-blocks with clock domains, FSM/SRAM allocation, BFM validation. Use for 'uarch', 'microarchitecture', 'Phase 3'."
user-invocable: true
argument-hint: "[--resume | uarch-focus]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute Phase 3 μArch design pipeline. Concretizes architecture blocks into
implementable microarchitecture specifications with clock domains, protocol
assignments, register/SRAM/FSM allocation, and BFM validation.
</Purpose>

<Use_When>
- Phase 2 architecture is complete and μArch design is needed
- User says "microarchitecture", "uarch", "Phase 3"
- Need detailed module specs before RTL implementation
</Use_When>

<Do_Not_Use_When>
- Phase 2 architecture is not complete (run p2-arch-design first)
- Already have μArch specs and need RTL (use rtl-p4-implement)
- Need architecture-level design (use p2-arch-design)
</Do_Not_Use_When>

## Prerequisites

Phase 2 completion required:
- `docs/phase-2-architecture/architecture.md` must exist
- `refc/` directory with C reference model must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p2-arch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p3-uarch-orchestrator",
     prompt="Execute Phase 3 uArch design. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages domain consultation, parallel uarch design + BFM
development, BFM validation gate, and 5-reviewer dynamic-convergence review (min 2, max 5 rounds).

## Workflow Notes

- Open Resolution: resolve all OPEN-2-* items from Phase 2 `open-requirements.json`
- Zero-Opens Invariant: no unresolved OPEN-* items may pass to Phase 4
- Compliance Check: verify REQ-U-* uarch requirements against P1+P2 iron requirements
- Exit gate includes `compliance-pass` and `zero-remaining-opens`

## P3 Exit Gate: Acceptance Criteria Advisory

Every REQ-U-* in `docs/phase-3-uarch/iron-requirements.json` should have ≥1 `acceptance_criteria` entry.
This is an advisory check (WARNING, not hard-block):
- If any REQ-U-* has no `acceptance_criteria` (absent or empty array `[]`): emit WARNING listing
  the affected REQ IDs
- Prompt uarch-designer to add missing criteria before P3 exit
- Proceed even if some REQ-U-* lack AC — downstream verification will operate at req_ids level
  (backward compatible)

## P3 Exit Gate: Decomposition Completeness Advisory

After iron-requirements.json is finalized, verify decomposition completeness:
1. Read docs/phase-1-research/iron-requirements.json — collect all Critical/High REQ-F-*
2. Read docs/phase-2-architecture/iron-requirements.json — collect all Critical/High REQ-A-*
3. For each Critical/High REQ-F-*: check if at least one REQ-U-* has it in `traces_to`
4. For each Critical/High REQ-A-*: check if at least one REQ-U-* has it in `traces_to`
5. Report:
   - COVERED: upstream REQ has ≥1 REQ-U-* tracing to it
   - UNCOVERED: no REQ-U-* traces to this upstream REQ → WARNING

This is advisory (WARNING, not hard-block). UNCOVERED Critical requirements
should be investigated — they may indicate a decomposition gap or an intentional
architecture decision (document rationale if intentional).
