---
name: rtl-p5s-cdc-verify
description: "P5 CDC analysis: finds missing synchronizers and metastability risks, emits SDC constraints. Use for multi-clock designs or pre-synthesis CDC signoff."
user-invocable: true
argument-hint: "[top-module]"
allowed-tools: Read, Write, Edit, Task, Grep, Glob
---

Delegate using the current host as described in `{plugin_root}/runtime/model-selection.md`.

<Purpose>
Perform static CDC analysis on RTL to identify missing synchronizers, metastability risks,
and CDC constraint gaps. Record the evidence for the requested module or the whole design.

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

| Scope | CDC report | Constraints |
| --- | --- | --- |
| Whole design | `reviews/phase-5-verify/cdc-report.md` | `syn/constraints/cdc_constraints.sdc` |
| Named module | `reviews/phase-5-verify/{module}-cdc-report.md` | `syn/constraints/cdc_constraints_{module}.sdc` |

The report records the selected engine, observed findings and effective timing exceptions.
Open checks remain INCOMPLETE when the required tool or measurement is unavailable.
