# Weighted Prediction — H.264 & H.265

> References: H.264 §8.4.2.3; H.265 §8.5.3.3.4

## Overview

Weighted prediction adjusts inter-prediction samples with per-reference weights and offsets, primarily for fade/cross-fade compensation.

| Mode | Description | Slice Types |
|------|-------------|-------------|
| Default | Simple average for bi-prediction | P, B |
| Explicit | Per-slice weight/offset signaled | P (weighted_pred_flag), B (weighted_bipred_idc) |
| Implicit | POC-distance-based weights (H.264 only) | B (weighted_bipred_idc=2) |

## Default Prediction (No Weighting)

### Uni-Prediction (P-slice or single-direction B)

`predSample = predL0[x][y]` (or predL1)

No weighting applied; prediction sample used directly.

### Bi-Prediction (B-slice)

`predSample = (predL0[x][y] + predL1[x][y] + 1) >> 1`

Simple average with rounding offset of 1.

## Explicit Weighted Prediction

### Syntax (Slice Header)

| Field | Bits | Description |
|-------|------|-------------|
| `luma_log2_weight_denom` | 3 (H.264) / 3 (H.265) | Denominator = `1 << luma_log2_weight_denom` |
| `chroma_log2_weight_denom` | 3 / 3 | Chroma denominator (separate) |
| `luma_weight_lX_flag[i]` | 1 per ref | Weight present for ref i, list X |
| `chroma_weight_lX_flag[i]` | 1 per ref | Chroma weight present |
| `luma_weight_lX[i]` | se(v) | Weight value (signed) |
| `luma_offset_lX[i]` | se(v) | Offset value (signed) |
| `chroma_weight_lX[i][j]` | se(v) | Per-component (Cb, Cr) |
| `chroma_offset_lX[i][j]` | se(v) | Per-component offset |

**Default weight** (when flag=0): `weight = 1 << log2_weight_denom`, `offset = 0`.

### Value Ranges

| Parameter | H.264 Range | H.265 Range |
|-----------|-------------|-------------|
| `luma_log2_weight_denom` | 0..7 | 0..7 |
| `chroma_log2_weight_denom` | 0..7 | 0..7 |
| `luma_weight` | -128..127 | -128..127 |
| `luma_offset` | -128..127 | -(1<<(bitDepth-1))..((1<<(bitDepth-1))-1) |
| `chroma_weight` | -128..127 | -128..127 |
| `chroma_offset` | -128..127 | -128..127 (after adjustment) |

### Uni-Prediction Formula (§8.4.2.3.1 / §8.5.3.3.4)

```
predSample = Clip3(0, maxVal,
    ((predLX[x][y] * weight + (1 << (log2WD - 1))) >> log2WD) + offset)
```

where `log2WD = luma_log2_weight_denom` (or chroma variant).

**Special case**: When `log2WD = 0`:
`predSample = Clip3(0, maxVal, predLX[x][y] * weight + offset)`

### Bi-Prediction Formula (§8.4.2.3.2 / §8.5.3.3.4)

```
predSample = Clip3(0, maxVal,
    (predL0[x][y] * w0 + predL1[x][y] * w1 + ((o0 + o1 + 1) << log2WD)) >> (log2WD + 1))
```

where:
- `w0 = luma_weight_l0[refIdxL0]`, `w1 = luma_weight_l1[refIdxL1]`
- `o0 = luma_offset_l0[refIdxL0]`, `o1 = luma_offset_l1[refIdxL1]`
- `log2WD = luma_log2_weight_denom`

**Rounding offset**: `(o0 + o1 + 1) << log2WD` ensures correct rounding when combining two weighted predictions.

## H.264 Implicit Weighted Prediction (weighted_bipred_idc=2)

Weights derived from POC distance (no syntax overhead):

```
td = Clip3(-128, 127, DiffPicOrderCnt(refL1, refL0))
tb = Clip3(-128, 127, DiffPicOrderCnt(curPic, refL0))

if (td != 0) {
    tx = (16384 + Abs(td/2)) / td
    distScaleFactor = Clip3(-1024, 1023, (tb * tx + 32) >> 6)
    w1 = distScaleFactor >> 2
    w0 = 64 - w1
} else {
    w0 = 32; w1 = 32
}
```

Applied as: `predSample = Clip1((predL0 * w0 + predL1 * w1 + 32) >> 6)`

**log2_weight_denom** is implicitly 5 for implicit mode.

**Note**: H.265 does not support implicit weighted prediction. Only default and explicit modes are available.

## H.265-Specific Details

### Chroma Offset Adjustment (§7.4.7.3)

H.265 adjusts chroma offsets to account for weight scaling:

```
chroma_offset_lX[i][j] = Clip3(-128, 127,
    raw_offset + ((128 * (1 << chroma_log2_weight_denom) - 128 * chroma_weight) >> chroma_log2_weight_denom))
```

This ensures neutral gray (128) maps correctly after weight application.

### WP with High Bit Depth

For 10-bit content:
- Offset range: -512..511 (luma), -128..127 (chroma, after adjustment)
- `maxVal = (1 << bitDepth) - 1` = 1023
- Accumulator needs: bitDepth + 8 (weight) + 1 (sign) = 19 bits for uni-pred

## Hardware Implementation Notes

### Datapath Width Analysis

| Operation | Accumulator Width (8-bit) | Accumulator Width (10-bit) |
|-----------|--------------------------|---------------------------|
| Uni-pred: `pred * weight` | 8 + 8 = 16 bits signed | 10 + 8 = 18 bits signed |
| Uni-pred: `+ offset` | 16 + 1 = 17 bits signed | 18 + 1 = 19 bits signed |
| Bi-pred: `p0*w0 + p1*w1` | 8 + 8 + 1 = 17 bits signed | 10 + 8 + 1 = 19 bits signed |
| Bi-pred: `+ offset_sum` | 17 + 8 = 25 bits (conservative) | 19 + 10 = 29 bits |
| After shift + clip | 8-bit output | 10-bit output |

### Architecture

```
predL0 ──┬──[x w0]──┐
          │          ├──[+]──[+ offset]──[>> shift]──[clip]──> output
predL1 ──┴──[x w1]──┘
```

| Component | Resources | Notes |
|-----------|-----------|-------|
| Multipliers | 2 (bi-pred) or 1 (uni-pred) | 8x8 or 10x8 multiply |
| Adder | 1 (accumulate + offset) | 17-19 bit |
| Shifter | 1 (barrel, 0-8 positions) | log2WD + 1 range |
| Clipper | 1 (saturate to [0, maxVal]) | Compare + mux |

**Throughput**: 1 sample/cycle for uni-pred, 1 sample/cycle for bi-pred (2 multiplies can be parallel).

### Weight Storage

| Storage | Entries | Width | Total |
|---------|---------|-------|-------|
| Luma weights L0 | 16 (H.264) / 15 (H.265) | 8 bits | 16 bytes |
| Luma offsets L0 | 16 / 15 | 8 bits (or 10 for HBD) | 16 bytes |
| Luma weights L1 | 16 / 15 | 8 bits | 16 bytes |
| Luma offsets L1 | 16 / 15 | 8 bits | 16 bytes |
| Chroma (2 components) | 4x above | — | 128 bytes |
| **Total** | — | — | ~192 bytes |

Stored once per slice; updated on slice header parse.
