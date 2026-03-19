---
name: refactor-policy
description: "Passive policy for controlled RTL refactoring. Defines auto-fix allowed scope and prohibited changes requiring approval."
user-invocable: false
---

# Refactor Policy

## Refactor Classes
- `SAFE`: behavior-preserving cleanup with no interface/timing contract impact
- `RESTRICTED`: likely behavior-preserving but affects structure or test assumptions
- `PROHIBITED`: behavior/spec contract may change

## SAFE (auto-apply allowed)
- Naming/format consistency fixes
- Dead code removal
- Local duplication cleanup with equivalent logic
- Comment/documentation synchronization

## RESTRICTED (approval or explicit orchestrator permit)
- Significant module decomposition/merge
- Testbench structure reshaping affecting check points
- Constraint file reorganization without semantic change proof

## PROHIBITED (manual approval required)
- FSM semantic changes
- Pipeline latency/stage changes
- CDC strategy changes
- Interface contract changes
- Reset behavior semantics changes

## Pass/Fail Gate
- `FAIL`: any prohibited change applied without approval
- `FAIL`: equivalence confidence not demonstrated for SAFE/RESTRICTED changes
- `PASS`: only SAFE changes applied and mandatory recheck passed

## Escalation
- Any ambiguity about behavior equivalence: escalate as `RESTRICTED`
- Any proposal touching interface/timing contract: escalate before edit
- Repeated recheck fail after 2 attempts: stop and hand off with root-cause note

## Output Format
Use the following refactor execution report:

```markdown
# Refactor Execution Report
- Scope: module|block|top
- Verdict: PASS | FAIL

## Planned Changes
| ID | Class | Target | Rationale | Approval Required |
|---|---|---|---|---|

## Applied Changes
| ID | Files | Summary | Risk |
|---|---|---|---|

## Blocked/Deferred
- [approval-required or risky items]
```
