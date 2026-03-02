---
description: "Tier 3 module-level regression: cocotb multi-seed regression comparing RTL against reference models. Absorbs rtl-regression-run. Produces Requirement Traceability Matrix."
argument-hint: "[module-name --seeds=N]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Execute functional verification with multi-seed regression.

Delegate to the p5s-func-verify-orchestrator agent:

Task(subagent_type="rtl-agent-team:p5s-func-verify-orchestrator",
     prompt="Execute functional verification. User input: $ARGUMENTS")

Do not perform any work directly. The orchestrator agent manages pipelined TB generation,
multi-seed parallel regression, coverage analysis, and requirement traceability.
