---
paths:
  - "rtl/**/*.sv"
  - "rtl/**/*.svh"
  - "rtl/**/*.v"
  - "rtl/**/*.vh"
---

# Mandatory Verification After RTL Changes

**Passing lint does NOT equal functional correctness. Lint is necessary but not sufficient.**

## Required Steps (all 4 mandatory)

| Step | Description | Command |
|------|-------------|---------|
| 1. Modify | Change RTL code | — |
| 2. Lint | Pass lint | `verilator --lint-only -Wall` |
| 3. TB | Create/update testbench | `sim/{module}/tb_{module}.sv` |
| 4. Sim | Run simulation and PASS | cocotb or verilator |

**Anti-pattern**: `RTL modify → lint pass → "done"` — This is NOT done.
**Correct flow**: `RTL modify → lint pass → TB create/update → simulation PASS → "done"`

## Gate Signals

- Verification complete: `touch .rat/state/rtl-verify-done`
- Non-functional change waiver: `touch .rat/state/rtl-verify-waiver`

Hook enforcement: `PostToolUse:Edit/Write` tracks .sv modifications; `Stop` hook blocks exit without verification.

<!-- rat-version: 0.7.7 -->
