---
name: syn-tool-profiles
description: "Passive synthesis tool profiles (yosys, dc_shell, genus) for replayable runs and comparable summary outputs."
user-invocable: false
---

# Synthesis Tool Profiles

## Common Contract
- Prefer wrapper: `syn/scripts/run_syn.sh`
- Synthesis is mandatory at block/top gate levels.
- Normalize output into:
  - `tool`, `status`, `area`, `timing_summary`, `log_path`, `replay_path`

## Open-Source Baseline
- `yosys`:
  - `syn/scripts/run_syn.sh --tool yosys --top <top> -f rtl/filelist_top.f --outdir syn/reports`
  - Optional lib mapping:
    - `syn/scripts/run_syn.sh --tool yosys --top <top> -f rtl/filelist_top.f --liberty <lib> --outdir syn/reports`

## Commercial Profiles
- `dc_shell`:
  - `syn/scripts/run_syn.sh --tool dc_shell --top <top> -f rtl/filelist_top.f --outdir syn/reports`
  - Optional:
    - `--liberty <tech.lib> --script <dc.tcl>`
- `genus`:
  - `syn/scripts/run_syn.sh --tool genus --top <top> -f rtl/filelist_top.f --script <genus.tcl> --outdir syn/reports`

## Gate Criteria
- `FAIL`: tool fatal error, netlist generation failure, or unusable report
- `PASS`: synthesis completes and required summary artifacts are generated
