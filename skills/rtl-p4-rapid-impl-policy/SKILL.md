---
name: rtl-design-policy
description: "Policy for P4 rapid RTL implementation and block sanity integration. Defines quick-loop gates, failure handling, and minimum quality bars."
user-invocable: false
---

# RTL Design Policy (P4)

## Gate Priority
- Functional correctness is mandatory.
- Lint and CDC must be clean at module and block sanity scope.

## P4 Minimum Gates
- Lint PASS (module + touched integration scope)
- CDC PASS (module + touched crossings)
- Smoke functional PASS
- Block sanity integration PASS

## State Template Note
- `templates/p4-state.json` initializes `modules` as an empty map.
- The orchestrator populates concrete module keys at runtime from discovered targets.

## Rapid-Mode Gate Scope

The 4 gates above (lint, CDC, smoke, block sanity) are a minimal subset of the full
10-Wave pipeline defined in `rtl-p4-implement-policy`. The rapid-mode orchestrator
intentionally skips Waves 4-5 (code review), Wave 8 (protocol), Wave 9 (refactoring),
and Stream B artifact generation. Use `rtl-p4-implement` for the full pipeline.

## Failure Handling
- Prefer smallest-scope fix and re-run.
- If repeated failure on same category, escalate with root-cause summary.
