# compare_3way.py Worked Example

Tiny 3-way comparison vector set for `scripts/compare_3way.py`. The toy DUT
computes `y = (x * 3 + 1) mod 2^32` over 16 shared input words; the three
model outputs were produced from `vectors/test_vectors.hex`.

| Path | Role |
|------|------|
| `vectors/test_vectors.hex` | 16 shared input words (one 32-bit hex value per line — all three models consume the identical file). |
| `outputs_consistent/` | ref/BFM/RTL outputs that all match — the PASS baseline. |
| `outputs_rtl_drift/` | Same set, but RTL drifts at vector 11 (off-by-one rounding: `0x000258ca` → `0x000258c9`) — demonstrates the "RTL has a bug" diagnosis. |

Note: the script consumes line-oriented text (`--format hex|bin|csv`), so
these example files use `.hex`. In a real project run, binary model outputs
must first be dumped in one of these text formats.

## Run 1 — consistent set (expected: exit 0)

```sh
python3 ../scripts/compare_3way.py \
    --refc outputs_consistent/ref_output.hex \
    --bfm  outputs_consistent/bfm_output.hex \
    --rtl  outputs_consistent/rtl_output.hex \
    --format hex
```

All three pairs report `16/16 MATCH` → `OVERALL: CONSISTENT`.

## Run 2 — RTL drift set (expected: exit 1)

```sh
python3 ../scripts/compare_3way.py \
    --refc outputs_rtl_drift/ref_output.hex \
    --bfm  outputs_rtl_drift/bfm_output.hex \
    --rtl  outputs_rtl_drift/rtl_output.hex \
    --format hex
```

Output (abridged):

```
refC ↔ BFM   16  MATCH
refC ↔ RTL   15  MISMATCH
BFM ↔ RTL    15  MISMATCH

refC ↔ RTL first divergence at index 11:
  val_a=0x000258ca  val_b=0x000258c9  diff=1

OVERALL: INCONSISTENT
```

Diagnosis per `references/model-consistency-conventions.md` §3:
`ref == BFM != RTL` → **RTL has a bug**. The LLM writes this diagnosis (plus
the mismatch details table) into `sim/consistency/consistency_report.md`
using `templates/consistency-report.md`.
