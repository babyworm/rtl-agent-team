---
name: rtl-p7-exploration
description: "Phase 7: free exploration of algorithm alternatives and optimization experiments, exempt from pipeline rules. Triggers: 'explore', 'Phase 7'."
user-invocable: true
argument-hint: "[exploration topic]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 7 free exploration. Investigates algorithm alternatives, optimization
experiments, and technology evaluations without pipeline gate constraints.
</Purpose>

<Use_When>
- User says "Phase 7", "exploration", "explore", "free exploration"
- Want to investigate design alternatives without modifying production RTL
- Need ADR-documented exploration results for future pipeline integration
</Use_When>

<Do_Not_Use_When>
- Need formal design review with quality scoring (use rtl-p6-design-review)
- Need to modify production RTL (use rtl-p4-implement or rtl-p4s-refactor)
- Requirements or architecture are still being established (use earlier phases)
</Do_Not_Use_When>

## Prerequisites

Phase 6 completion is recommended but NOT required.
Phase 7 is **exempt from pipeline rules** (Rule 9) — free exploration allowed.

## Execution

Task(subagent_type="rtl-agent-team:p7-exploration-orchestrator",
     prompt="Execute Phase 7 exploration. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator manages guard rails, exploration agent dispatch,
ADR creation, and result documentation.
