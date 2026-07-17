# parse_coverage.py Worked Examples

Demonstrates deterministic coverage extraction (Execution step 2) from the two
artifact formats the `rtl-p5s-func-verify` pipeline actually produces
(`scripts/merge_coverage.sh`).

| File | Role |
|------|------|
| `merged.info` | Input 1: lcov tracefile as emitted by `verilator_coverage --write-info` (the `sim/coverage/merged.info` merge artifact). Two files, line (DA) records only. |
| `merged_coverage.json` | Output 1: JSON produced by the first command below. Line 80% vs 90% target → FAIL; toggle/fsm N/A (lcov carries no such data). |
| `coverage.dat` | Input 2: raw Verilator coverage database (`# SystemC::Coverage-3`, keyed `C '<key>' <count>` entries with `\x01`/`\x02` field separators). Carries v_line, v_branch, v_toggle, and v_user points. |
| `dat_coverage.json` | Output 2: JSON produced by the second command below. FSM 66.67% vs 70% target → FAIL; line/toggle PASS; branch informational (no default target). |

## Commands

Run from this directory:

```sh
python3 ../scripts/parse_coverage.py merged.info -o merged_coverage.json
python3 ../scripts/parse_coverage.py coverage.dat -o dat_coverage.json
```

Expected reports (both exit 1 — overall FAIL):

```
Wrote merged_coverage.json: overall_verdict=FAIL uncovered=4
Wrote dat_coverage.json: overall_verdict=FAIL uncovered=5
```

## What to check in the output

- Percentages are computed from the actual records — never fabricated. Metrics
  with no data report `pct: null` and `verdict: "N/A"` (lcov input: toggle/fsm).
- `v_user` coverage points in `.dat` are counted as the `fsm` metric (Verilator
  has no native FSM point type; user points are the pipeline's FSM convention).
- Uncovered bins are ranked deterministically: fsm > branch > line > toggle,
  then file/line/detail. In `dat_coverage.json` the uncovered
  `fsm_state DRAIN->IDLE` transition ranks 1, ahead of the uncovered branch on
  line 44.
- `branch` has no default project target → `verdict: "N/A"` unless
  `--target-branch` is passed.
- No timestamps: re-running the commands reproduces the committed JSON
  byte-for-byte (locked by `tests/unit/test_parse_coverage.py`).
- Interpretive gap classification (high-value vs unreachable) is NOT in the
  JSON — that stays with the `coverage-analyst` agent per the skill's
  `<Responsibility_Boundary>`.
