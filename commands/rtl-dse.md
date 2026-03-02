---
description: "This skill should be used for deep Design Space Exploration covering spec analysis, in-depth algorithm study, architecture exploration with multiple candidates, and reference C model creation or transformation from a user-provided functional model. Covers Phase 1→2 with emphasis on algorithmic trade-offs and architectural alternatives."
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute deep Design Space Exploration through Phase 1 (Research + Algorithm Exploration)
and Phase 2 (Architecture DSE + Reference C Model).

Delegate to the dse-orchestrator agent:

Task(subagent_type="rtl-agent-team:dse-orchestrator",
     prompt="Execute Design Space Exploration pipeline. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages input mode detection,
deep algorithm exploration, architecture candidate comparison, user decision points,
C model transformation, and quality gates.
