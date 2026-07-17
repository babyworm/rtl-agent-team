# Model Consistency Conventions

A quick reference for `rtl-model-consistency`. Stays under 150 lines so it can be
consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Test vector set | `sim/consistency/test_vectors.bin` | shared across all three models |
| Ref model output | `sim/consistency/ref_output.hex` | from `refc/build/ref_model` |
| BFM output | `sim/consistency/bfm_output.hex` | from `bfm/build/bfm_smoke` |
| RTL output | `sim/consistency/rtl_output.hex` | from iverilog/cocotb simulation |
| Output file format | line-oriented text, one value per line (`hex`/`bin`/`csv`) | dump binary outputs to text first |
| Consistency report | `sim/consistency/consistency_report.md` | pairwise comparison matrix |
| Comparison script | `skills/rtl-model-consistency/scripts/compare_3way.py` | pairwise diff + diagnosis |
| Report template | `skills/rtl-model-consistency/templates/consistency-report.md` | scaffold |
| RTL port convention | `i_`/`o_` prefix, `{domain}_clk`, `{domain}_rst_n` | `i_pixel_data`, `sys_clk` |

## 2. Output schema

### consistency_report.md structure
```markdown
# 3-Way Consistency Report
Generated: {date}  Vectors: {N}

## Summary
| Pair         | Match | Mismatch |
|--------------|-------|---------|
| ref == BFM   |  48   |    2    |
| ref == RTL   |  50   |    0    |
| BFM == RTL   |  48   |    2    |

## Diagnosis
ref == RTL != BFM → BFM has diverged from ref model.

## Mismatch Details
| Pair       | First Divergence Index | Expected (val_a) | Actual (val_b) |
|------------|------------------------|------------------|----------------|
| ref vs BFM | 142                    | 0x0000003a       | 0x0000003b     |
```

### compare_3way.py CLI and output contract
```sh
python3 compare_3way.py --refc ref_output.hex --bfm bfm_output.hex \
    --rtl rtl_output.hex [--format hex|bin|csv] [--tolerance 0]
```
All three `--refc/--bfm/--rtl` file arguments are required; inputs are
line-oriented text (one value per line; `#`/`//` comment lines skipped).
The script prints to stdout:
- a data-length line per model, then the pairwise summary table
  (`Pair / Compared / Match / Mismatch / Verdict`) for refC↔BFM,
  refC↔RTL, and BFM↔RTL
- per mismatching pair: `first divergence at index N:` with
  `val_a=0x... val_b=0x... diff=...`
- `OVERALL: CONSISTENT` (exit 0) or `OVERALL: INCONSISTENT` (exit 1)

## 3. Comparison criteria and diagnosis logic

| Result pattern | Diagnosis |
|----------------|-----------|
| ref == BFM == RTL | All models consistent — PASS |
| ref == BFM != RTL | RTL has a bug |
| ref == RTL != BFM | BFM has diverged from ref model |
| BFM == RTL != ref | Ref model diverged; RTL and BFM agree |
| ref != BFM != RTL | Three-way mismatch — cannot auto-diagnose; report all divergences |

- **Bitexact** is the default criterion unless a tolerance is explicitly documented in
  `reviews/phase-3-uarch/bfm-feature-coverage.md` or `reviews/phase-2-architecture/ref-model-feature-coverage.md`.
- Minimum vector set: 10 vectors when `sim/consistency/test_vectors.bin` is absent.
  Prefer 50 vectors for full regression; 500 for pre-tape-out gate.
- All three models must run on **identical** input vectors — no subset comparisons.

## 4. Anti-patterns

- Running only two-model comparison and declaring consistency — misses BFM drift that
  causes `rtl-p5s-perf-verify` to produce a wrong baseline.
- Using different input files for different models — comparisons are invalid.
- Accepting partial match (e.g., "48/50 vectors pass") — all vectors must pass before
  reporting PASS; partial results are a FAIL.
- Running consistency check when models are known to be out of sync — fix the diverging
  model first, then re-run.
- Reporting a divergence index without the expected/actual values — makes divergence
  non-actionable for the developer who must fix the bug.
