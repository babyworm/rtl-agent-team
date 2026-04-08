---
name: rtl-p5s-cdc-verify
description: "This skill should be used when analyzing clock domain crossings for synchronizer coverage and metastability risks."
user-invocable: true
argument-hint: "[top-module]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Perform static CDC analysis on RTL to identify missing synchronizers, metastability risks,
and CDC constraint gaps. Outputs: lint/cdc/cdc_report.md + syn/constraints/cdc_constraints.sdc.

See `references/cdc-patterns.md` for synchronizer types, common violations, and SDC constraint templates.
</Purpose>

<Use_When>
- RTL design has multiple clock domains
- Pre-synthesis CDC sign-off required
- New clock domain or crossing signal added to existing design
- CDCcheck in pre-tapeout checklist
</Use_When>

<Do_Not_Use_When>
- Design is single-clock (CDC analysis not applicable)
- Only functional simulation needed
- Synthesis timing analysis needed (use rtl-synth-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
CDC bugs are among the hardest to find in simulation because metastability is
non-deterministic. Static analysis catches structural CDC violations reliably
before they become intermittent silicon failures.
</Why_This_Exists>

## Prerequisites

RTL modules required with multiple clock domains:
- `rtl/**/*.sv` files must exist with `{domain}_clk` signals

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p5s-cdc-orchestrator",
     prompt="Execute CDC verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages clock domain identification, cross-domain analysis,
SDC constraint generation, and optional commercial CDC tool integration.

## Output

- `reviews/phase-5-verify/{module}-cdc-report.md` — CDC analysis with VIOLATION/CAUTION/PASS verdict
- `syn/constraints/cdc_constraints.sdc` — generated SDC constraints for identified crossings
