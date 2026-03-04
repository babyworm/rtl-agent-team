---
name: cdc-tool-profiles
description: "Passive CDC tool profiles (structural, spyglass, vc_cdc, questa_cdc) and classification conventions."
user-invocable: false
---

# CDC Tool Profiles

## Common Contract
- Prefer wrapper: `sim/cdc/run_cdc.sh`
- Output classes:
  - `VIOLATION`
  - `CAUTION`
  - `INFO`
- Gate fail when unwaived `VIOLATION` exists.

## Open-Source Baseline
- `structural`:
  - `sim/cdc/run_cdc.sh --tool structural --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`

## Commercial Profiles
- `spyglass`:
  - `sim/cdc/run_cdc.sh --tool spyglass --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`
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
