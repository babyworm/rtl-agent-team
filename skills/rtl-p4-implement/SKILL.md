---
name: rtl-p4-implement
description: "Implement SystemVerilog RTL modules from uarch specs in Phase 4. Produces lint-clean, code-reviewed, unit-tested, CDC/protocol-checked rtl/*/*.sv through a 10-Wave pipeline."
user-invocable: true
argument-hint: "[module-list or --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 4 RTL implementation pipeline. Implements SystemVerilog modules from
μArch specs through a 10-Wave pipeline: Write → Lint → Fix → Review → Bugfix →
UnitTest → CDC → Protocol → Refactor → IntegrationGate.
</Purpose>

<Use_When>
- Phase 3 μArch specs are complete and RTL coding is needed
- User says "implement RTL", "write RTL", "Phase 4", "code modules"
- Need lint-clean, unit-tested SystemVerilog modules
</Use_When>

<Do_Not_Use_When>
- Phase 3 μArch specs are not complete (run rtl-p3-uarch-design first)
- Only need a single module bug fix (use rtl-p4s-bugfix)
- Need RTL + verification together from uarch (use rtl-uarch-to-verify)
</Do_Not_Use_When>

## Prerequisites

Phase 3 completion required:
- At least one μArch spec in `docs/phase-3-uarch/` must exist

If prerequisite is missing, inform the user to run `/rtl-agent-team:rtl-p3-uarch-design` first.

## Execution

Task(subagent_type="rtl-agent-team:p4-implement-orchestrator",
     prompt="Execute Phase 4 RTL implementation. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages module enumeration, 10-Wave sequencing,
parallel task dispatch, and phase gate verification.
