---
name: sim-tool-profiles
description: "Passive simulation tool profiles for replayable execution (verilator, iverilog, vcs, xrun, questa)."
user-invocable: false
---

# Simulation Tool Profiles

## Common Contract
- Prefer wrapper: `scripts/run_sim.sh`
- Every run must emit:
  - primary log path
  - replay script path
  - pass/fail summary

## Open-Source Baseline
- `verilator`:
  - `scripts/run_sim.sh --sim verilator --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports --trace`
- `iverilog`:
  - `scripts/run_sim.sh --sim iverilog --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports`

## Commercial Profiles
- `vcs`:
  - `scripts/run_sim.sh --sim vcs --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports`
- `xrun`:
  - `scripts/run_sim.sh --sim xrun --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports`
- `questa`:
  - `scripts/run_sim.sh --sim questa --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports`

## Normalized Result Fields
- `tool`
- `status` (`pass` or `fail`)
- `errors_count`
- `warnings_count`
- `log_path`
- `replay_path`
