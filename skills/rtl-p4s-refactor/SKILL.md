---
name: rtl-p4s-refactor
description: "This skill should be used when restructuring RTL code without behavioral change. Applies naming conventions and verifies equivalence."
user-invocable: true
---

<Purpose>
Refactor existing RTL for improved readability, maintainability, or lint compliance
without changing functional behavior. Verifies equivalence after refactoring.
</Purpose>

<Use_When>
- RTL exists but has structural problems (naming, style, lint violations)
- Module needs to be split or merged without behavioral change
- Preparing RTL for review or handoff
</Use_When>

<Do_Not_Use_When>
- Behavioral change is needed (use rtl-p4-implement for new implementation)
- Only lint checking needed without fixing (use rtl-lint-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
Refactoring RTL is risky without equivalence verification — a "cosmetic" rename can break
a signal connection. Combining rtl-architect analysis with lint-checker verification provides safety.
</Why_This_Exists>

<Delegation>
The orchestrator handles structural analysis, refactoring implementation,
lint verification, and equivalence checking.

All policies, checklists, naming convention rules, and escalation rules
are defined in the rtl-p4s-refactor-policy skill (loaded via the
orchestrator's skills: field).

## Execution

Task(subagent_type="rtl-agent-team:p4s-refactor-orchestrator",
     prompt="Execute RTL refactoring cycle. Target: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages the full analyze → refactor → lint → equivalence cycle.

## Output

- Refactored RTL file(s) with lint re-pass confirmation
- Equivalence verification report confirming no behavioral change
</Delegation>

<Examples>
<Good>
Split 800-line module into 3 focused modules; lint-checker confirms clean; smoke sim passes same vectors as before.
</Good>
<Bad>
Refactoring signal names without checking all instantiation sites — breaks hierarchical connections silently.
</Bad>
</Examples>
