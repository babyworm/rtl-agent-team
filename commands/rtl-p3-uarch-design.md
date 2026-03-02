---
description: "Phase 3 uArch design. Concretizes P2 modules into sub-blocks with clock domains, protocol assignment, register/SRAM/FSM allocation. Validates via TLM-based BFM with per-block I/O logging."
argument-hint: "[--resume | uarch-focus]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute Phase 3 uArch design pipeline.

Delegate to the p3-uarch-orchestrator agent:

Task(subagent_type="rtl-agent-team:p3-uarch-orchestrator",
     prompt="Execute Phase 3 uArch design. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages domain consultation,
parallel uarch design + BFM development, BFM validation gate, and 5-reviewer 3-round review.
