---
description: "Phase 5 verification orchestrator: three-stage (module→top→final) parallel verification pipeline covering lint, SVA/formal, CDC, protocol, functional regression, coverage, performance, synthesizability estimation, and code review."
argument-hint: "[--module=name | --stage=N | --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute Phase 5 verification pipeline.

Delegate to the p5-verify-orchestrator agent:

Task(subagent_type="rtl-agent-team:p5-verify-orchestrator",
     prompt="Execute Phase 5 verification. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages all stages,
module graduation, parallel agent spawning, and compliance review.
