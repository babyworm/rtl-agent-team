---
description: "This skill should be used when implementing RTL and running verification from existing microarchitecture documents (Phase 4→5). Requires completed Phase 1-3 artifacts as prerequisites. Produces RTL code, unit tests, and full verification with Phase 5→4 feedback loops — stopping before Design Note phase."
argument-hint: "[resume or module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute the Phase 4→5 pipeline (RTL Implementation → Verification) from existing
Phase 1-3 design documents.

Delegate to the uarch-to-verify-orchestrator agent:

Task(subagent_type="rtl-agent-team:uarch-to-verify-orchestrator",
     prompt="Execute Phase 4→5 RTL implementation and verification pipeline. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages prerequisite
verification, dual-stream Phase 4, sub-phase Phase 5, feedback loops, and
state management.
