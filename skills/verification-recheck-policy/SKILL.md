---
name: verification-recheck-policy
description: "Passive policy defining minimum re-validation matrix by change type after review/refactor work."
user-invocable: false
---

# Verification Recheck Policy

## Minimum Matrix
- Style-only change: lint
- Logic refactor (behavior-preserving intent): lint + functional smoke/regression + RTL-vs-RTL equivalence
- Interface-impact change: lint + cdc + functional regression (+ equivalence when change is declared behavior-preserving)
- Constraint/synthesis-impact change: lint + cdc + functional + synthesis/timing rerun + equivalence (RTL-vs-netlist or RTL-vs-RTL)

## Recommended Commands (open-source baseline)
- Lint:
  - `lint/scripts/run_lint.sh --tool verilator -f rtl/filelist_top.f --outdir lint/lint`
- CDC:
  - `lint/scripts/run_cdc.sh --tool structural --top <top> -f rtl/filelist_top.f --outdir lint/cdc`
- Functional smoke/regression:
  - `scripts/run_sim.sh --sim verilator --top <tb_top> -f rtl/filelist_top.f --outdir sim/reports`
  - `bash skills/rtl-p5s-func-verify/scripts/run_regression.sh --mode local --seeds "1 42 123 1337 65536" --sim verilator`
- Synthesis/timing recheck:
  - `syn/scripts/run_syn.sh --tool yosys --top <top> -f rtl/filelist_top.f`
  - If STA wrapper exists: `syn/scripts/run_sta.sh --tool opensta --top <top> --outdir syn/rpt`
- Equivalence recheck:
  - Delegate to equivalence-checker with context:
    - RTL-vs-RTL after refactor/ECO (`reference=<pre-change>`, `implementation=<post-change>`)
    - RTL-vs-netlist after synthesis-impact change (`reference=rtl`, `implementation=syn/netlist.v`)

## Pass/Fail Criteria
- `lint`: zero errors
- `cdc`: no unwaived `VIOLATION`
- `functional`: all must-pass scenarios green
- `regression`: all required seeds pass (or documented waiver)
- `synthesis/timing`: run completes with no fatal tool error
- `equivalence`: no unresolved non-equivalent points (counterexamples must be resolved or approved as intentional deltas)

## Escalation
- Same category fails twice after fix attempts: escalate with replay script path
- CDC or synthesis/timing failure after interface change: escalate to design owner
- Missing replay artifacts: re-run command to generate reproducible evidence
- Equivalence FAIL/UNKNOWN after behavior-preserving claim: escalate immediately (potential unintended semantic change)

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
