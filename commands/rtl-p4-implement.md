---
description: "Implement SystemVerilog RTL modules from uarch specs in Phase 4. Produces lint-clean, code-reviewed, unit-tested, CDC/protocol-checked rtl/*/*.sv through a 10-Wave pipeline."
argument-hint: "[module-list or --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute Phase 4 RTL implementation pipeline.

Delegate to the p4-implement-orchestrator agent:

Task(subagent_type="rtl-agent-team:p4-implement-orchestrator",
     prompt="Execute Phase 4 RTL implementation. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages module enumeration,
10-Wave sequencing, parallel task dispatch, and phase gate verification.
