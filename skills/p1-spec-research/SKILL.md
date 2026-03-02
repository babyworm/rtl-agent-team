---
name: p1-spec-research
description: "Phase 1 spec research. Refines spec precisely, collects missing information via AskUserQuestion and domain-consult, surveys candidate algorithms/tools with trade-offs, and proposes options matching user requirements."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
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

## Prerequisites

None — this is the first phase entry point.

## Execution

Task(subagent_type="rtl-agent-team:p1-research-orchestrator",
     prompt="Execute Phase 1 spec research. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages spec refinement, solution tree exploration,
sub-domain expert coordination, and 3-round chief review.
