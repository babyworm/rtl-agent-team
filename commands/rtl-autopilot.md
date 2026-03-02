---
description: "This skill should be used when starting a full RTL design pipeline from spec to verification. Orchestrates 6-phase flow (Research → Architecture → μArch → RTL → Verify → Design Note) with dual-layer phase gates and hierarchical spec compliance."
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute the full RTL design pipeline from specification to verified silicon.

Delegate to the autopilot-orchestrator agent:

Task(subagent_type="rtl-agent-team:autopilot-orchestrator",
     prompt="Execute full RTL autopilot pipeline. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages all phases,
agent spawning, and quality gates.
