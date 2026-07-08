---
name: rat-p1p3-spec-uarch
description: "Sequential Phase 1-3 pipeline (research, architecture, uArch, BFM); stops before RTL for human review. Use for 'spec to uarch', 'design only'."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute the Phase 1→3 pipeline (Research → Architecture → μArch) with enforced
dual-layer phase gates, then STOP for human review before RTL implementation.
Produces all design documents needed for RTL coding.
</Purpose>

<Use_When>
- Need complete design documents before RTL implementation
- Want human review checkpoint between design and implementation
- User says "spec to uarch", "design only", "Phase 1 to 3"
- Starting from scratch and want to stop before RTL coding
</Use_When>

<Do_Not_Use_When>
- Already have uarch docs and need RTL implementation (use rat-p4p5-impl-verify)
- Need the full pipeline including RTL (use rat-auto-design)
- Only need a single phase (use the phase-specific skill)
</Do_Not_Use_When>

## Prerequisites

None — this pipeline starts from Phase 1.

## Execution

Task(subagent_type="rtl-agent-team:spec-to-uarch-orchestrator",
     prompt="Execute Phase 1→3 spec-to-uarch pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages phase sequencing, 3-round iterative reviews,
quality gates, ADR recording, and state management.
