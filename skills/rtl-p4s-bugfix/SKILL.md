---
name: rtl-p4s-bugfix
description: "RTL bug fix workflow enforcing the full cycle: analyze → fix → lint → TB create/update → functional verification. Prevents RTL changes from being considered complete with lint-only validation."
user-invocable: true
---

<Purpose>
A workflow skill that enforces the design-to-verification flow when fixing RTL bugs.
A fix is only considered complete after TB generation and functional simulation pass — not just lint.

**Core principle: lint is only a syntax check, not evidence of functional correctness.**

This skill integrates with the PostToolUse:Edit hook tracking system.
Modified .sv files are automatically tracked, and session termination is blocked without functional verification.
</Purpose>

<Use_When>
- Fixing RTL bugs found during Phase 4 review
- Fixing functional errors in RTL modules
- Adding or modifying functionality in existing RTL
- Verifying no functional regression after refactoring
- Fixing integration bugs spanning multiple modules
- **Phase 5→4 Feedback Loop**: Automatic fix path invoked when Phase 5 verification FAILs
</Use_When>

<Do_Not_Use_When>
- Coding convention changes only (e.g., port renaming with no functional change) → use rtl-p4s-refactor
- Writing a new module from scratch → use rtl-p4-implement
- Simple lint error fixes (e.g., removing unused signals) → use rtl-lint-check
</Do_Not_Use_When>

<Why_This_Exists>
Born from a previous session where 9 RTL bugs were fixed with only lint runs, skipping TB/simulation entirely.
Passing lint is merely "compilation success" — simulation is required to prove the fix is functionally correct.

**Anti-pattern example:**
- 312 lines of RTL modified across 5 Waves → only verilator --lint-only executed → 0 TBs, 0 simulations
- Result: declared "complete" with zero functional correctness verification
</Why_This_Exists>

<Delegation>
The orchestrator handles analysis, fix+lint, TB creation/update, functional verification,
Phase 5→4 feedback return, parallel UNIT_FIX across modules, and lesson-learned recording.

All policies, checklists, escalation rules, and parallel fix decision logic are defined
in the rtl-p4s-bugfix-policy skill (loaded via the orchestrator's skills: field).

## Execution

Task(subagent_type="rtl-agent-team:p4s-bugfix-orchestrator",
     prompt="Execute RTL bug fix cycle. Bug description: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages the full analyze → fix → lint → TB → simulation cycle.

## Output

- Fixed RTL file(s) with lint re-pass confirmation
- Updated or new testbench with passing functional simulation results
- `.rat/scratch/phase-4/bugfix-decision-{N}.md` — decision record documenting root cause, fix rationale, and verification evidence
</Delegation>
