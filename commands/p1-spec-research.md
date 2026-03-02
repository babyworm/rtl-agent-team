---
description: "Phase 1 spec research. Refines spec precisely, collects missing information via AskUserQuestion and domain-consult, surveys candidate algorithms/tools with trade-offs, and proposes options matching user requirements."
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute Phase 1 spec research pipeline.

Delegate to the p1-research-orchestrator agent:

Task(subagent_type="rtl-agent-team:p1-research-orchestrator",
     prompt="Execute Phase 1 spec research. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages spec refinement,
solution tree exploration, sub-domain expert coordination, and 3-round chief review.
