---
name: rtl-autopilot
description: "This skill should be used when starting a full RTL design pipeline from spec to verification. Orchestrates 6-phase flow (Research → Architecture → μArch → RTL → Verify → Design Note) with dual-layer phase gates and hierarchical spec compliance."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute the full RTL design pipeline from specification to verified silicon.
Orchestrates all 6 phases with dual-layer phase gates, parallel agent execution,
feedback loops, and resumability.
</Purpose>

<Use_When>
- Starting a complete RTL design from a specification document
- User says "design a chip", "full pipeline", "RTL design", "autopilot"
- Need end-to-end flow: Research → Architecture → μArch → RTL → Verify → Design Note
</Use_When>

<Do_Not_Use_When>
- Only need a specific phase (use the phase-specific skill instead)
- Only need design space exploration (use rtl-dse)
- Only need design documents without RTL (use rtl-spec-to-uarch)
</Do_Not_Use_When>

## Prerequisites

None — this is the full pipeline entry point. Setup is handled by the orchestrator's Step 0.

## Execution

Task(subagent_type="rtl-agent-team:autopilot-orchestrator",
     prompt="Execute full RTL autopilot pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages all phases, agent spawning, and quality gates.
