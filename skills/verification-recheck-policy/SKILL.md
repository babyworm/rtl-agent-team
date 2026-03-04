---
name: verification-recheck-policy
description: "Passive policy defining minimum re-validation matrix by change type after review/refactor work."
user-invocable: false
---

# Verification Recheck Policy

## Minimum Matrix
- Style-only change: lint
- Logic refactor: lint + functional smoke/regression
- Interface-impact change: lint + cdc + functional regression
- Constraint/synthesis-impact change: lint + cdc + functional + synthesis/timing rerun

## Recommended Commands (open-source baseline)
- Lint:
  - `lint/scripts/run_lint.sh --tool verilator -f rtl/filelist_top.f --outdir lint/reports`
- CDC:
  - `sim/cdc/run_cdc.sh --tool structural --top <top> -f rtl/filelist_top.f --outdir sim/cdc/reports`
- Functional smoke/regression:
  - `scripts/run_sim.sh --sim verilator --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports`
  - `bash skills/rtl-regression-run/scripts/run_regression.sh --mode local --seeds "1 42 123 1337 65536" --sim verilator`
- Synthesis/timing recheck:
  - `syn/scripts/run_syn.sh --tool yosys --top <top> -f rtl/filelist_top.f --outdir syn/reports`
  - If STA wrapper exists: `syn/scripts/run_sta.sh --tool opensta --top <top> --outdir syn/reports`

## Pass/Fail Criteria
- `lint`: zero errors
- `cdc`: no unwaived `VIOLATION`
- `functional`: all must-pass scenarios green
- `regression`: all required seeds pass (or documented waiver)
- `synthesis/timing`: run completes with no fatal tool error

## Escalation
- Same category fails twice after fix attempts: escalate with replay script path
- CDC or synthesis/timing failure after interface change: escalate to design owner
- Missing replay artifacts: re-run command to generate reproducible evidence

## Output Format
```markdown
# Recheck Report
- Change Type: [style|logic|interface|constraint]
- Verdict: PASS | FAIL

## Executed Checks
| Check | Command | Result | Artifact |
|---|---|---|---|

## Failures and Escalation
- [if any]
```
