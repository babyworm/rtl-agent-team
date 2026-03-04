---
name: rtl-silicon-validation-policy
description: "Policy for P5B silicon validation. Defines block/top synthesis, constraints quality, timing-oriented checks, and signoff readiness criteria."
user-invocable: false
---

# Silicon Validation Policy (P5B)

## Scope
- Block and top level only.

## Mandatory Checks
- Constraints quality and syntax validation
- Synthesis PASS on block/top
- CDC/timing signoff checklist pass
- Top integration precision regression PASS

## Hard Gate
- P5A functional closure must be PASS before P5B can pass.
