# Model Consistency Report: {{MODULE_NAME}}

> Generated: {{DATE}}
> Test vectors: {{VECTOR_SOURCE}}
> Tolerance: {{TOLERANCE}} (0 = bitexact)

## Pairwise Comparison

| Pair | Samples | Match | Mismatch | Verdict |
|------|---------|-------|----------|---------|
| refC ↔ BFM | {{N}} | {{MATCH}} | {{MISMATCH}} | {{PASS/FAIL}} |
| refC ↔ RTL | {{N}} | {{MATCH}} | {{MISMATCH}} | {{PASS/FAIL}} |
| BFM ↔ RTL | {{N}} | {{MATCH}} | {{MISMATCH}} | {{PASS/FAIL}} |

## Overall Verdict: {{CONSISTENT/INCONSISTENT}}

## First Divergence Details

### refC ↔ BFM
- Index: {{INDEX}}
- refC value: `0x{{VAL_A}}`
- BFM value: `0x{{VAL_B}}`
- Possible cause: {{ANALYSIS}}

### refC ↔ RTL
- Index: {{INDEX}}
- refC value: `0x{{VAL_A}}`
- RTL value: `0x{{VAL_B}}`
- Possible cause: {{ANALYSIS}}

## Test Vector Summary

| Property | Value |
|----------|-------|
| Vector count | {{COUNT}} |
| Input format | {{FORMAT}} |
| Source | {{SPEC_OR_RANDOM}} |
| Seed (if random) | {{SEED}} |

## Recommendations

- {{ACTION_ITEMS}}
