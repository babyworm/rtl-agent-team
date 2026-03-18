---
name: rtl-functional-verify-policy
description: "Policy for P5A functional closure. Defines hierarchy-level verification depth, coverage goals, and requirement traceability gates."
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
  - All Critical/High ac_ids must have VERIFIED or FORMAL status
  - NOT_VERIFIABLE ac_ids documented but excluded from gate
  - UNTESTED or PARTIAL Critical/High ac_ids → FAIL (blocks P6 entry; PARTIAL must be upgraded to VERIFIED or FORMAL)
When no structured AC: existing closure gate applies.
