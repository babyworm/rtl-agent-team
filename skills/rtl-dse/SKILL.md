---
name: rtl-dse
description: "This skill should be used for deep Design Space Exploration covering spec analysis, in-depth algorithm study, architecture exploration with multiple candidates, and reference C model creation or transformation from a user-provided functional model. Covers Phase 1→2 with emphasis on algorithmic trade-offs and architectural alternatives."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute deep Design Space Exploration through Phase 1 (Research + Algorithm Exploration)
and Phase 2 (Architecture DSE + Reference C Model). Emphasizes algorithmic trade-offs,
multiple architecture candidates, user decision points, and optional C model transformation.
</Purpose>

<Use_When>
- Need to explore multiple algorithm/architecture candidates before committing
- User says "DSE", "design space exploration", "compare architectures"
- Have an existing functional model to transform into HW-friendly form
- Want deep algorithm study with trade-off analysis
</Use_When>

<Do_Not_Use_When>
- Already have architecture decided (use p2-arch-design or rtl-p4-implement)
- Need the full pipeline including RTL and verification (use rat-auto-design)
- Only need spec research without architecture exploration (use p1-spec-research)
</Do_Not_Use_When>

## Prerequisites

None — DSE is an independent exploration entry point.

## Execution

Task(subagent_type="rtl-agent-team:dse-orchestrator",
     prompt="Execute Design Space Exploration pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages input mode detection, deep algorithm exploration,
architecture candidate comparison, user decision points, C model transformation,
and quality gates.
