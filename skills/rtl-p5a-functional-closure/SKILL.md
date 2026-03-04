---
name: rtl-p5a-functional-closure
description: "Phase 5A functional verification closure across module, block, and top pre-integration checkpoints. Functional correctness is the absolute priority gate."
user-invocable: true
argument-hint: "[module-list or --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run deep functional verification closure after P4 sanity gates.
Coverage and requirement traceability are enforced at module/block/top scope.
</Purpose>

<Use_When>
- P4 implementation/sanity passed and deep functional validation is needed
- Need multi-seed regression, corner cases, and traceability closure
- Prefer split Phase-5 flow: run `rtl-p5a-functional-closure` first, then `rtl-p5b-silicon-validation`
- Replacing legacy bundled Phase-5 entry (`rtl-p5-verify`) with explicit functional-first closure
</Use_When>

<Do_Not_Use_When>
- P4 has unresolved lint/cdc/smoke issues
- Primary goal is synthesis/timing/signoff (use rtl-p5b-silicon-validation)
- Need one legacy bundled Phase-5 command for functional+silicon checks (use `rtl-p5-verify`)
</Do_Not_Use_When>

## Execution

Task(subagent_type="rtl-agent-team:p5a-functional-closure-orchestrator",
     prompt="Execute Phase 5A functional closure. User input: $ARGUMENTS")

Do not perform work directly.
The orchestrator controls hierarchy-level functional gates.
