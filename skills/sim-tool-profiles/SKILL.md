---
name: sim-tool-profiles
description: "Internal reference: sim tool profiles (agent-loaded; do not invoke)."
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

## Invocation Reference

The exact binaries and switches `run_sim.sh` uses per simulator. These are the
shapes each vendor documents; changing them silently breaks the stage.

| Simulator | Compile | Elaborate | Run |
|-----------|---------|-----------|-----|
| `verilator` | `verilator --binary` (or `--cc`) | — | generated executable |
| `iverilog` | `iverilog -g2012` | — | `vvp` |
| `vcs` | `vcs -full64 -sverilog +v2k -o <exe>` | (compile produces `simv`) | `<exe>` |
| `xrun` | `xrun -compile -sv -xmlibdirname <lib>` | `xrun -elaborate -sv -xmlibdirname <lib> -top <tb>` | `xrun -R -xmlibdirname <lib>` |
| `questa` | `vlib work` + `vlog -sv -work work` | `vopt +acc -work work <tb> -o <tb>_opt` | `vsim -c -work work <tb>_opt -do "..."` |

**Xcelium gotcha**: `-compile` only parses and analyses — it does not write a
snapshot. `-R` reinvokes an *existing* snapshot without recompiling or
re-elaborating, so the `-elaborate` step is what makes `-R` work at all. All three
steps must name the same `-xmlibdirname`.

## UVM Coverage Collection (Commercial Only)

Code coverage must be enabled at **both compile and runtime** for all commercial simulators.

| Simulator | Compile Flag | Runtime Flag | Coverage DB | Merge Tool |
|-----------|-------------|-------------|-------------|------------|
| VCS | `-cm line+cond+fsm+tgl+branch` | `-cm line+cond+fsm+tgl+branch -cm_dir <dir>.vdb` | `.vdb` directory | `urg -dir *.vdb -format both` |
| Xcelium | `-coverage all` | `-coverage all -covworkdir <dir>/cov_work -covscope tb_top` | `cov_work/` directory | `imc -exec merge.tcl` |
| Questa | `+cover=bcestf` (at `vlog`) | `-coverage` (at `vsim`) + `-do "coverage save -onexit <file>.ucdb"` | `.ucdb` file | `vcover merge out.ucdb *.ucdb` |

**Questa gotcha**: `+cover=bcestf` at `vlog` compile is **mandatory** — runtime `-coverage` alone collects nothing.

UVM regression runner: `{plugin_root}/skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh` (`{plugin_root}` = plugin root from `.rat/state/spawn-context.json`)
- Handles compile-once + parallel multi-seed execution + coverage merge per simulator
- Targets: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%, branch ≥ 80%, functional ≥ 95%

## Normalized Result Fields
- `tool`
- `status` (`pass` or `fail`)
- `errors_count`
- `warnings_count`
- `log_path`
- `replay_path`
