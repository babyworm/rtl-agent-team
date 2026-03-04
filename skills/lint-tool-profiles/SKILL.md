---
name: lint-tool-profiles
description: "Passive lint tool profiles (verilator, verible, slang, spyglass) with unified report expectations."
user-invocable: false
---

# Lint Tool Profiles

## Common Contract
- Prefer wrapper: `lint/scripts/run_lint.sh`
- All profiles must normalize output into:
  - `errors`, `warnings`, `tool`, `log_path`, `replay_path`
- Gate decision is based on normalized `errors == 0`

## Open-Source Baseline
- `verilator`:
  - `lint/scripts/run_lint.sh --tool verilator -f rtl/filelist_top.f --outdir lint/reports`
- `verible`:
  - `lint/scripts/run_lint.sh --tool verible -f rtl/filelist_top.f --outdir lint/reports`
- `slang`:
  - `lint/scripts/run_lint.sh --tool slang -f rtl/filelist_top.f --outdir lint/reports`

## Commercial Profile
- `spyglass`:
  - `lint/scripts/run_lint.sh --tool spyglass --top <top> -f rtl/filelist_top.f --outdir lint/reports`

## Severity Mapping
- Tool `error/fatal` -> normalized `error`
- Tool `warning` -> normalized `warning`
- Unknown parse line -> keep raw log reference and mark parse caution
