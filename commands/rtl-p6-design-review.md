---
description: "Phase 6: Design Review & Documentation with 2-round consistency checks, detailed design notes with decision rationale, and PDF generation support."
argument-hint: "[options]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute Phase 6: Design Review & Documentation pipeline after Phase 5 verification passes.

Delegate to the p6-review-orchestrator agent:

Task(subagent_type="rtl-agent-team:p6-review-orchestrator",
     prompt="Execute Phase 6 design review and documentation pipeline. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages Phase 5→6 gate check,
2-wave parallel execution, 2-round consistency checks (CC1, CC2), completion quality gate,
and optional PDF generation.
