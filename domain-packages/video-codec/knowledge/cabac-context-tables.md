# CABAC Context Model Tables — H.264 & H.265

> References: H.264 §9.3; H.265 §9.3

## CABAC Engine Overview

| Property | H.264 | H.265 |
|----------|-------|-------|
| Context models | ~460 | ~154 (significantly reduced) |
| State variable | pStateIdx (0-63) + valMPS | pStateIdx (0-63) + valMPS |
| Range precision | 9 bits (codIRange) | 9 bits (ivlCurrRange) |
| Offset precision | 9 bits (codIOffset) | 9 bits (ivlOffset) |
| Bypass mode | Yes (equiprobable bins) | Yes |
| Terminate mode | Yes (end_of_slice) | Yes (end_of_slice_segment) |

## H.264 Context Initialization (§9.3.1)

### Initialization Parameters

Each context model is initialized from `(m, n)` pairs using:

```
preCtxState = Clip3(1, 126, ((m * Clip3(0, 51, SliceQP)) >> 4) + n)
```

Then:
- If `preCtxState <= 63`: `pStateIdx = 63 - preCtxState`, `valMPS = 0`
- If `preCtxState > 63`: `pStateIdx = preCtxState - 64`, `valMPS = 1`

### Init Tables per Slice Type

| cabac_init_idc | Slice Type | Description |
|----------------|------------|-------------|
| 0 | I-slice | Intra-only contexts |
| 1 | P-slice (set 1) | Inter + intra contexts |
| 2 | P-slice (set 2) | Alternative inter init |
| — | B-slice | Uses cabac_init_idc 0, 1, or 2 |

**Context index ranges** (H.264 Table 9-11 through 9-23):

| Syntax Element | ctxIdx Range | Count | Notes |
|----------------|-------------|-------|-------|
| mb_type (I-slice) | 0-10 | 11 | Includes I_NxN, I_16x16 variants |
| mb_type (P-slice) | 14-20 | 7 | P_L0, P_8x8, etc. |
| mb_type (B-slice) | 27-35 | 9 | B_Direct, B_L0, B_L1, B_Bi |
| sub_mb_type | 21-26, 36-39 | 10 | Sub-macroblock partitions |
| mvd_lX | 40-46 (x), 47-53 (y) | 14 | MV difference bins |
| ref_idx_lX | 54-59 | 6 | Reference index |
| mb_qp_delta | 60-63 | 4 | QP delta |
| intra_chroma_pred_mode | 64-67 | 4 | Chroma mode |
| prev_intra4x4_pred_mode | 68 | 1 | Intra mode flag |
| rem_intra4x4_pred_mode | 69 | 1 | Remaining intra mode |
| coded_block_flag | 85-104 | 20 | CBF per block type |
| significant_coeff_flag | 105-165 | 61 | Significance map |
| last_significant_coeff_flag | 166-226 | 61 | Last significant position |
| coeff_abs_level_minus1 | 227-275 | 49 | Coefficient levels |

### Context Derivation (Neighbor-Based)

Most contexts use spatial neighbors for derivation:

```
ctxIdxInc = condTermFlagA + condTermFlagB
```

where `condTermFlagA` = condition from left neighbor, `condTermFlagB` = condition from above neighbor. This yields ctxIdxInc in {0, 1, 2}.

## H.265 Context Initialization (§9.3.2)

### Initialization Formula

```
slopeIdx = (initValue >> 4) * 5 - 45
offsetIdx = ((initValue & 15) << 3) - 16
preCtxState = Clip3(1, 126, ((slopeIdx * Clip3(0, 51, SliceQP)) >> 4) + offsetIdx)
```

Then same mapping to `(pStateIdx, valMPS)` as H.264.

### Init Types

| initType | Slice Type | cabac_init_flag |
|----------|------------|-----------------|
| 0 | I-slice | — |
| 1 | P-slice | 0 |
| 2 | P-slice | 1 |
| 1 | B-slice | 1 |
| 2 | B-slice | 0 |

### Context Index Mapping (§9.3.4, Table 9-4)

| Syntax Element | ctxIdx Start | Count | Notes |
|----------------|-------------|-------|-------|
| sao_merge_flag | 0 | 1 | SAO merge |
| sao_type_idx | 1 | 1 | SAO type |
| split_cu_flag | 2 | 3 | CU quad-tree split (depth-based) |
| cu_transquant_bypass | 5 | 1 | Transform bypass |
| cu_skip_flag | 6 | 3 | Skip mode |
| pred_mode_flag | 9 | 1 | Intra vs inter |
| part_mode | 10 | 4 | Partition mode |
| prev_intra_luma_pred_flag | 14 | 1 | MPM flag |
| intra_chroma_pred_mode | 15 | 1 | Chroma mode |
| merge_flag | 16 | 1 | Merge mode |
| merge_idx | 17 | 1 | Merge candidate index |
| inter_pred_idc | 18 | 5 | L0/L1/Bi selection |
| ref_idx_lX | 23 | 2 | Reference index |
| mvp_lX_flag | 25 | 1 | AMVP index |
| split_transform_flag | 26 | 3 | TU split |
| cbf_luma | 29 | 2 | Luma coded block flag |
| cbf_chroma | 31 | 4 | Chroma coded block flag |
| abs_mvd_greater0 | 35 | 1 | MVD > 0 |
| abs_mvd_greater1 | 36 | 1 | MVD > 1 |
| cu_qp_delta_abs | 37 | 2 | QP delta |
| transform_skip_flag | 39 | 1 | Transform skip |
| last_sig_coeff_x_prefix | 40 | 18 | Last X position |
| last_sig_coeff_y_prefix | 58 | 18 | Last Y position |
| coded_sub_block_flag | 76 | 4 | Sub-block significance |
| sig_coeff_flag | 80 | 42 | Coefficient significance |
| coeff_abs_level_greater1 | 122 | 24 | Level > 1 |
| coeff_abs_level_greater2 | 146 | 6 | Level > 2 |

**Total**: ~154 context models (vs ~460 in H.264).

## State Transition Table (§9.3.3.2, Table 9-2)

Both H.264 and H.265 use the same 64-state probability model:

| Current State | LPS Coded | MPS Coded |
|---------------|-----------|-----------|
| pStateIdx | transIdxLPS[pStateIdx] | transIdxMPS[pStateIdx] |

**Key transition entries**:

| pStateIdx | transIdxLPS | transIdxMPS | Approx. p(LPS) |
|-----------|-------------|-------------|-----------------|
| 0 | 0 | 1 | 0.500 |
| 1 | 0 | 2 | 0.474 |
| 7 | 4 | 8 | 0.348 |
| 15 | 10 | 16 | 0.225 |
| 31 | 23 | 32 | 0.085 |
| 47 | 38 | 48 | 0.024 |
| 62 | 56 | 62 | 0.006 |
| 63 | 56 | 63 | 0.005 (nearly certain MPS) |

**Adaptation rate**: Approximately `p_new = 0.96 * p_old + 0.04 * observed` (exponential moving average).

## Renormalization (§9.3.3.2.2)

### Range Table (rangeTabLPS, Table 9-1)

Indexed by `pStateIdx` (6 bits) and `qCodIRangeIdx` (2 bits, from top 2 bits of codIRange):

| pStateIdx | qIdx=0 | qIdx=1 | qIdx=2 | qIdx=3 |
|-----------|--------|--------|--------|--------|
| 0 | 128 | 176 | 208 | 240 |
| 1 | 128 | 167 | 197 | 227 |
| 10 | 95 | 104 | 123 | 142 |
| 30 | 37 | 48 | 57 | 65 |
| 50 | 6 | 8 | 9 | 11 |
| 62 | 2 | 2 | 2 | 2 |

**Table size**: 64 states x 4 range bins = 256 entries x 9 bits = 288 bytes.

After coding a bin, renormalize: while `codIRange < 256`, shift left and read one bit from bitstream.

## Hardware Implementation Notes

### Context Memory

| Storage | Entries | Width | Total |
|---------|---------|-------|-------|
| H.264 context states | 460 | 7 bits (6 state + 1 MPS) | 403 bytes |
| H.265 context states | 154 | 7 bits | 135 bytes |
| rangeTabLPS ROM | 256 | 9 bits | 288 bytes |
| transIdxLPS ROM | 64 | 6 bits | 48 bytes |
| transIdxMPS ROM | 64 | 6 bits | 48 bytes |

### Pipeline Architecture (Typical)

| Stage | Operation | Critical Path |
|-------|-----------|---------------|
| 1 | Context address generation (syntax element + neighbor) | ctxIdx computation |
| 2 | Context read + range table lookup | SRAM read |
| 3 | Range subdivision (codIRange - codIRangeLPS) | 9-bit subtraction |
| 4 | MPS/LPS decision + range update | Compare + mux |
| 5 | Renormalization (count leading zeros + shift) | CLZ + barrel shift |
| 6 | Context state update (write-back) | Table lookup + SRAM write |

**Throughput limitation**: 1 bin/cycle (context-coded). Bypass bins can achieve 2+ bins/cycle since no context read/write needed.

### Multi-Bin Acceleration

- **Bypass mode**: No context dependency; multiple bins decoded in parallel
- **Syntax elements with fixed context**: sig_coeff_flag scanning can pipeline context reads
- **Context grouping**: H.265 reduced context count enables single-port SRAM (vs dual-port for H.264)
