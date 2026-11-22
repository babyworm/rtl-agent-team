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

- Verification complete: `scripts/run_sim.sh` records `.rat/state/verify-evidence.json` after a measured PASS. A project's own runner records the same evidence through the plugin's `eda_runner.py verify-run --root <project> -f <filelist> [--log <summary>] [--remote-host <host> --remote-root <dir>] -- <runner>`; the runner prints `RAT_SIM_PASS` or `TESTS=<n> PASS=<n> FAIL=0`.
- Gate mode: `verification.stop_gate` in `rat_config.json` is `block` (default), `notify` (a notice, no block) or `off`. Changing it is the user's decision; ask first, as for a waiver.
- Non-functional change waiver: the user's decision; ask before creating `.rat/state/rtl-verify-waiver`.

Hook enforcement: `PostToolUse:Edit/Write` tracks .sv modifications; `Stop` hook keeps Claude working until verification is done, then hands the decision to the user.

<!-- rat-version: 2.0.1 -->
