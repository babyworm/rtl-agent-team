---
description: "Phase 2 architecture design. Reviews P1 algorithm candidates for HW implementation feasibility, designs block-level data paths, builds reference C model, and iterates with 3-round review."
argument-hint: "[--resume | architecture-focus]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute Phase 2 architecture design pipeline.

Delegate to the p2-arch-orchestrator agent:

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Execute Phase 2 architecture design. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages P1 candidate HW review,
parallel architecture design + ref model, 3-round iterative review, and artifact finalization.
