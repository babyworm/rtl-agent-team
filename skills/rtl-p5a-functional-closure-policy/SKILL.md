---
name: rtl-p5a-functional-closure-policy
description: "Internal reference: rtl p5a functional closure policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Functional Verification Policy (P5A)

## Scope
- Module, block, and top functional closure.

## Mandatory Checks
- Multi-seed regression for functional stability
- Coverage closure per project target
- Requirement traceability matrix complete

## Hard Gate
- Functional FAIL blocks progression to silicon validation.

## AC-Level P5A Closure (when applicable)
P5A functional closure includes AC coverage when structured acceptance_criteria exist:

  **During P5A internal verification (module/block checkpoints):**
  - PARTIAL Critical/High ac_ids = WARNING (continue verification, attempt to upgrade)
  - UNTESTED Critical/High ac_ids = FAIL (must add tests before proceeding)

  **At P5A exit gate (gates P5B entry and ultimately P6):**
  - All Critical/High ac_ids must have VERIFIED or FORMAL status
  - UNTESTED or PARTIAL Critical/High ac_ids → FAIL (blocks P5B/P6 entry; PARTIAL must be upgraded to VERIFIED or FORMAL)
  - NOT_VERIFIABLE ac_ids documented but excluded from gate

When no structured AC: existing closure gate applies.
