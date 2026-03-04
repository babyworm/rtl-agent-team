---
name: rtl-p5b-silicon-validation
description: "Phase 5B silicon validation for block/top signoff readiness. Runs synthesis, constraints, timing-oriented checks, and top integration precision checks after functional closure."
user-invocable: true
argument-hint: "[--top <name>]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run silicon-readiness validation after functional closure PASS.
Focus: constraints, synthesis, CDC/STA signoff posture, and precise top integration checks.
</Purpose>

<Use_When>
- Functional closure has passed and silicon risk reduction is required
- Need block/top synthesis and timing-oriented validation
- Following split flow after `rtl-p5a-functional-closure` with explicit signoff-oriented stage separation
- Preferred replacement for legacy bundled `rtl-p5-verify` when teams adopt split P5A/P5B
</Use_When>

<Do_Not_Use_When>
- Functional closure has not passed
- You only need module-level quick checks
- Need one legacy bundled Phase-5 command for functional+silicon checks (use `rtl-p5-verify`)
</Do_Not_Use_When>

## Execution

Task(subagent_type="rtl-agent-team:p5b-silicon-validation-orchestrator",
     prompt="Execute Phase 5B silicon validation. User input: $ARGUMENTS")

Do not perform work directly.
The orchestrator enforces signoff-oriented gates.
