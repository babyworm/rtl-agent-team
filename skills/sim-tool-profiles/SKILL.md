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

## UVM Coverage Collection (Commercial Only)

Code coverage must be enabled at **both compile and runtime** for all commercial simulators.

| Simulator | Compile Flag | Runtime Flag | Coverage DB | Merge Tool |
|-----------|-------------|-------------|-------------|------------|
| VCS | `-cm line+cond+fsm+tgl+branch` | `-cm line+cond+fsm+tgl+branch -cm_dir <dir>.vdb` | `.vdb` directory | `urg -dir *.vdb -format both` |
| Xcelium | `-coverage all` | `-coverage all -covworkdir <dir>/cov_work -covscope tb_top` | `cov_work/` directory | `imc -exec merge.tcl` |
| Questa | `+cover=bcestf` (at `vlog`) | `-coverage` (at `vsim`) + `-do "coverage save -onexit <file>.ucdb"` | `.ucdb` file | `vcover merge out.ucdb *.ucdb` |

**Questa gotcha**: `+cover=bcestf` at `vlog` compile is **mandatory** — runtime `-coverage` alone collects nothing.

UVM regression runner: `skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh`
- Handles compile-once + parallel multi-seed execution + coverage merge per simulator
- Targets: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%, branch ≥ 80%, functional ≥ 95%

## Normalized Result Fields
- `tool`
- `status` (`pass` or `fail`)
- `errors_count`
- `warnings_count`
- `log_path`
- `replay_path`
