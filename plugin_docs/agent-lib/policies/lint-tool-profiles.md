# Lint Tool Profiles

## Common Contract
- Prefer wrapper: `lint/scripts/run_lint.sh`
- All profiles must normalize output into:
  - `errors`, `warnings`, `tool`, `log_path`, `replay_path`
- Gate decision is based on normalized `errors == 0`

## Open-Source Baseline
- `verilator`:
  - `lint/scripts/run_lint.sh --tool verilator -f rtl/filelist_top.f --outdir lint/lint`
- `verible`:
  - `lint/scripts/run_lint.sh --tool verible -f rtl/filelist_top.f --outdir lint/lint`
- `slang`:
  - `lint/scripts/run_lint.sh --tool slang -f rtl/filelist_top.f --outdir lint/lint`
  - **Auto-detects RTL vs TB** based on source file paths:
    - RTL (`rtl/`): runs with `-Weverything` for maximum strictness — catches `always_ff` multi-driver violations (VCS ICPD), uninitialized variables, width mismatches, etc.
    - TB (`sim/`): runs with `--allow-dup-initial-drivers` — permits `initial` + `always_ff` on same signal (common testbench pattern)
  - Use semantic elaboration when the task needs IEEE 1800 §9.2.2.4 checks; a style scan does not establish that scope.

## Commercial Profile
- `spyglass` (binary: `sg_shell`, config key: `sg_shell`, script flag: `--tool spyglass`):
  - `lint/scripts/run_lint.sh --tool spyglass --top <top> -f rtl/filelist_top.f --outdir lint/lint`
  - Note: `rat_config.json` uses `sg_shell` as tool key; runner scripts accept `--tool spyglass`

## Severity Mapping
- Tool `error/fatal` -> normalized `error`
- Tool `warning` -> normalized `warning`
- Unknown parse line -> keep raw log reference and mark parse caution
