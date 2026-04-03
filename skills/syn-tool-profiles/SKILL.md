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

## Tool Availability Tiers

| Tier | Tools | Capabilities | sv2v Handling |
|------|-------|-------------|---------------|
| 1 (commercial) | dc_shell, genus | Full synthesis + timing + area + PPA | Not needed (native SV support) |
| 2 (oss) | yosys | Latch detection, unmapped cells, basic area estimate | Script handles internally (Layer 2) |
| 3 (none) | — | Synthesis skipped with WARNING | N/A |

Use `get_synthesis_tier()` from `lib/tool-runner.sh` to determine tier at runtime.

**sv2v Policy**: sv2v is a **Layer 2 concern** — `run_syn.sh` handles it internally for Yosys.
Agent prompts and policy skills MUST NOT instruct manual sv2v execution.
Canonical source stays SystemVerilog; tool adaptation is the script's responsibility.

**`--skip-if-unavailable` flag**: When passed to `run_syn.sh`, tool absence or license failure
produces WARNING + clean exit (exit 0) instead of hard failure. Use in optional synthesis contexts
(Stream B smoke test, V8 estimation without commercial tools).

## Gate Criteria
- `FAIL`: tool fatal error, netlist generation failure, or unusable report
- `PASS`: synthesis completes and required summary artifacts are generated
- `SKIPPED`: tool not available and `--skip-if-unavailable` was set (non-blocking)
