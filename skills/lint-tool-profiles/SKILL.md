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
  - **Auto-detects RTL vs TB** based on source file paths:
    - RTL (`rtl/`): runs with `-Weverything` for maximum strictness — catches `always_ff` multi-driver violations (VCS ICPD), uninitialized variables, width mismatches, etc.
    - TB (`sim/`): runs with `--allow-dup-initial-drivers` — permits `initial` + `always_ff` on same signal (common testbench pattern)
  - Only slang catches IEEE 1800 §9.2.2.4 multi-driver violations; Verilator and Verible do not

## Commercial Profile
- `spyglass`:
  - `lint/scripts/run_lint.sh --tool spyglass --top <top> -f rtl/filelist_top.f --outdir lint/reports`

## Severity Mapping
- Tool `error/fatal` -> normalized `error`
- Tool `warning` -> normalized `warning`
- Unknown parse line -> keep raw log reference and mark parse caution
