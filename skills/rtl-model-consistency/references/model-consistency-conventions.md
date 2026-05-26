# Model Consistency Conventions

A quick reference for `rtl-model-consistency`. Stays under 150 lines so it can be
consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Test vector set | `sim/consistency/test_vectors.bin` | shared across all three models |
| Ref model output | `sim/consistency/ref_output.bin` | from `refc/build/ref_model` |
| BFM output | `sim/consistency/bfm_output.bin` | from `bfm/build/bfm_smoke` |
| RTL output | `sim/consistency/rtl_output.bin` | from iverilog/cocotb simulation |
| Consistency report | `sim/consistency/consistency_report.md` | per-vector comparison matrix |
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
| Vector | Pair       | Byte Offset | Expected | Actual |
|--------|------------|-------------|----------|--------|
| 023    | ref vs BFM | 142         | 0x3A     | 0x3B   |
```

### compare_3way.py output contract
The script must emit one result per vector with fields:
- `vector_id` — zero-padded integer string
- `ref_bfm` — `PASS` or `FAIL`
- `ref_rtl` — `PASS` or `FAIL`
- `bfm_rtl` — `PASS` or `FAIL`
- `first_divergence_byte` — integer or `null`

## 3. Comparison criteria and diagnosis logic

| Result pattern | Diagnosis |
|----------------|-----------|
| ref == BFM == RTL | All models consistent — PASS |
| ref == BFM != RTL | RTL has a bug |
| ref == RTL != BFM | BFM has diverged from ref model |
| BFM == RTL != ref | Ref model diverged; RTL and BFM agree |
| ref != BFM != RTL | Three-way mismatch — cannot auto-diagnose; report all divergences |

- **Bitexact** is the default criterion unless a tolerance is explicitly documented in
  `docs/phase-3-uarch/bfm-feature-coverage.md` or `reviews/phase-2-architecture/ref-model-feature-coverage.md`.
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
- Reporting byte offset without the expected/actual values — makes divergence
  non-actionable for the developer who must fix the bug.
