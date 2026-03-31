---
name: cdc-tool-profiles
description: "Passive CDC tool profiles (structural, slang-cdc, spyglass, vc_cdc, questa_cdc) and classification conventions."
user-invocable: false
---

# CDC Tool Profiles

## Common Contract
- Prefer wrapper: `sim/cdc/run_cdc.sh`
- Output classes:
  - `VIOLATION`
  - `CAUTION`
  - `CONVENTION`
  - `INFO`
  - `WAIVED`
- Gate fail when unwaived `VIOLATION` exists.

## Open-Source Baseline
- `structural` (grep heuristic + slang-cdc crosscheck):
  - `sim/cdc/run_cdc.sh --tool structural --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`
  - When `slang-cdc` is installed, automatically runs AST-based crosscheck after grep
  - Crosscheck reports: `sim/cdc/reports/slang-cdc/` (cdc_report.md, .json, .sdc, waivers.yaml)
  - Exit code: slang-cdc violation count when available, grep fallback otherwise
- `slang-cdc` (standalone AST-based, https://github.com/babyworm/slang-cdc):
  - `sim/cdc/run_cdc.sh --tool slang-cdc --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`
  - 8 synchronizer patterns (2-FF, 3-FF, gray, handshake, async FIFO, MUX, pulse, Johnson)
  - Quality checks: reconvergence, glitch path, fan-out-before-sync, reset sync, non-2^N FIFO
  - Outputs: md + json + sdc + waiver yaml
  - Install: `git clone https://github.com/babyworm/slang-cdc.git && make build && make install`

## Commercial Profiles
- `spyglass` (binary: `sg_shell`, config key: `sg_shell`, script flag: `--tool spyglass`):
  - `sim/cdc/run_cdc.sh --tool spyglass --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`
  - Note: `rat_config.json` uses `sg_shell` as tool key; runner scripts accept `--tool spyglass`
- `vc_cdc`:
  - `sim/cdc/run_cdc.sh --tool vc_cdc --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`
- `questa_cdc`:
  - `sim/cdc/run_cdc.sh --tool questa_cdc --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`

## Normalized Result Fields
- `tool`
- `violations_count`
- `cautions_count`
- `info_count`
- `report_path`
- `replay_path`
