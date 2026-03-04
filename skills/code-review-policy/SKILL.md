---
name: code-review-policy
description: "Passive policy for LLM code review findings, severity taxonomy, and evidence format."
user-invocable: false
---

# Code Review Policy

## Scope
- RTL logic correctness and spec/uarch compliance
- Testbench quality and checker/scoreboard adequacy
- Verification completeness (coverage + traceability)
- Silicon risk indicators (constraints/CDC/synthesis/timing impacts)

## Severity
- `S0 Blocker`: data corruption, protocol/safety breakage, hard spec violation
- `S1 Critical`: high silicon risk, functional failure likely under valid stimulus
- `S2 Major`: maintainability/test-quality issues with medium defect risk
- `S3 Minor`: style/readability/non-blocking improvements

## Pass/Fail Gate
- `FAIL`: any unresolved `S0` or `S1`
- `CONDITIONAL`: only `S2` findings remain and have approved remediation plan
- `PASS`: only `S3` or no findings

## Escalation
- Any `S0`: immediate stop, escalate to orchestrator/user with fix-first recommendation
- Repeated `S1` on same module after 2 fix loops: escalate to architecture owner
- Missing evidence for `S0/S1`: finding is invalid until evidence attached

## Evidence Rules
- Every `S0/S1` finding must include reproducible evidence:
  - file and line
  - failing command/log snippet
  - expected vs actual behavior
- Prefer replay artifacts (`*_latest.sh`, wave/report paths) over prose-only claims

## Output Format
Use the following report skeleton:

```markdown
# Code Review Report
- Scope: module|block|top
- Verdict: PASS | CONDITIONAL | FAIL

## Findings
| ID | Severity | File:Line | Summary | Evidence |
|---|---|---|---|---|

## Required Actions
| Priority | Owner | Action | Recheck |
|---|---|---|---|

## Escalations
- [if any]
```
