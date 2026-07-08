---
name: rtl-silicon-validation-policy
description: "Internal reference: rtl silicon validation policy (agent-loaded; do not invoke)."
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
- Equivalence validation when synthesis-significant optimization or ECO/refactor delta exists

## Conditional Expert Delegation (P5B)
- Invoke `equivalence-checker` when either condition is true:
  - Gate/netlist generated from updated constraints/synthesis flow must be proven equivalent to RTL
  - "Behavior-preserving" RTL ECO/refactor enters P5B signoff path
- Equivalence scope:
  - RTL-vs-netlist for synthesis outputs
  - RTL-vs-RTL for ECO/refactor delta verification
- Equivalence FAIL/UNKNOWN is signoff-blocking unless explicitly waived by user/design owner.

## Hard Gate
- P5A functional closure must be PASS before P5B can pass.
