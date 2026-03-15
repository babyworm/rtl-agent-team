# Deblocking Filter & Boundary Strength — H.264 & H.265

> References: H.264 §8.7; H.265 §8.7.2

## Overview

The deblocking filter smooths block boundaries to reduce visible artifacts from block-based coding. Applied in-loop (reconstructed samples are filtered before use as reference).

| Property | H.264 | H.265 |
|----------|-------|-------|
| Block boundary granularity | 4x4 | 8x8 (luma), 8x8 (chroma in some cases) |
| Boundary strength (Bs) range | 0-4 | 0-2 |
| Filter types | Normal (Bs 1-3), Strong (Bs 4) | Normal (Bs 1), Strong (Bs 2, conditional) |
| Edge orientation | Vertical then horizontal | Vertical then horizontal |
| Chroma filtering | Bs >= 2 only | Bs >= 2 only (different threshold) |

## H.264 Boundary Strength Derivation (§8.7.2.1)

### Bs Determination (per 4x4 edge)

Evaluate in priority order (first match determines Bs):

| Bs | Condition | Meaning |
|----|-----------|---------|
| 4 | Either p or q is intra AND edge is MB boundary | Strongest: intra MB edge |
| 3 | Either p or q is intra (not MB boundary) | Intra block (internal edge) |
| 2 | Either p or q has non-zero coded residual | Residual present |
| 1 | Different reference frames OR different MV count OR `abs(mvP - mvQ) >= 4` (1 full-pel) | Motion discontinuity |
| 0 | None of the above | No filtering |

Where `p` = block on one side, `q` = block on the other side of the edge.

**MV threshold**: `abs(mvP.x - mvQ.x) >= 4 OR abs(mvP.y - mvQ.y) >= 4` (quarter-pel units, so 4 = 1 integer pel).

### Filter Decision Thresholds (§8.7.2.2)

For each edge with Bs > 0, test filter activation:

```
alpha = alpha_table[Clip3(0, 51, QPavg + filterOffsetA)]
beta  = beta_table[Clip3(0, 51, QPavg + filterOffsetB)]
QPavg = (QPp + QPq + 1) >> 1
```

**Filter condition** (must pass for each sample pair):
```
abs(p0 - q0) < alpha  AND
abs(p1 - p0) < beta   AND
abs(q1 - q0) < beta
```

### Alpha/Beta Tables (Excerpts)

| QP+offset | alpha | beta |
|-----------|-------|------|
| 0-15 | 0 | 0 |
| 16 | 4 | 2 |
| 20 | 4 | 3 |
| 24 | 7 | 4 |
| 28 | 10 | 6 |
| 32 | 13 | 7 |
| 36 | 17 | 8 |
| 40 | 22 | 9 |
| 44 | 36 | 11 |
| 48 | 64 | 14 |
| 51 | 255 | 18 |

**filterOffsetA/B**: Signaled in slice header (`slice_alpha_c0_offset_div2`, `slice_beta_offset_div2`), range -12 to +12 in steps of 2.

### H.264 Normal Filter (Bs = 1, 2, 3)

Modifies up to 3 samples on each side (p0, p1, p2, q0, q1, q2):

```
// Core delta for p0 and q0:
delta = Clip3(-tc, tc, ((q0 - p0) * 4 + (p1 - q1) + 4) >> 3)
p0' = Clip1(p0 + delta)
q0' = Clip1(q0 - delta)
```

`tc = tc0_table[QPavg + offset] + (Bs > 2 ? 1 : 0)`

**p1 modification** (conditional on `abs(p2 - p0) < beta`):
```
p1' = p1 + Clip3(-tc0, tc0, (p2 + ((p0 + q0 + 1) >> 1) - 2*p1) >> 1)
```

Same structure for q1. p2/q2 not modified in normal filter.

### H.264 Strong Filter (Bs = 4)

Modifies up to 3 samples on each side with averaging:

**Luma strong filter** (when `abs(p2-p0) < beta AND abs(p0-q0) < ((alpha>>2)+2)`):
```
p0' = (p2 + 2*p1 + 2*p0 + 2*q0 + q1 + 4) >> 3
p1' = (p2 + p1 + p0 + q0 + 2) >> 2
p2' = (2*p3 + 3*p2 + p1 + p0 + q0 + 4) >> 3
```
Otherwise, falls back to a weaker 1-sample modification.

**Chroma** (Bs = 4, always strong):
```
p0' = (2*p1 + p0 + q1 + 2) >> 2
q0' = (2*q1 + q0 + p1 + 2) >> 2
```

## H.265 Boundary Strength Derivation (§8.7.2.5.4)

### Bs Determination (per 8x8 edge)

| Bs | Condition | Notes |
|----|-----------|-------|
| 2 | Either p or q is intra-coded | Intra boundary |
| 1 | `abs(mvP - mvQ) >= 4` (1 integer pel) OR different reference pictures OR different number of MVs | Motion discontinuity |
| 0 | None of the above | No filtering |

**Key difference from H.264**: No Bs=3 or Bs=4. No residual-based Bs (H.265 removed coded-residual check).

### Edge Filtering Order (§8.7.2)

1. **Vertical edges** (filter along horizontal direction): Process all CTU vertical edges left-to-right
2. **Horizontal edges** (filter along vertical direction): Process all CTU horizontal edges top-to-bottom

Within each direction, 8x8 grid boundaries are tested.

### Filter Decision (§8.7.2.5.2)

```
beta  = beta_table[Clip3(0, 51, QPL + beta_offset)]
tc    = tc_table[Clip3(0, 53, QPL + 2*(Bs-1) + tc_offset)]
QPL   = (QPp + QPq + 1) >> 1
```

**Decision condition** (per 4-sample line crossing the edge):
```
d = dp0 + dq0 + dp3 + dq3
where dp0 = abs(p2[0] - 2*p1[0] + p0[0])
      dq0 = abs(q2[0] - 2*q1[0] + q0[0])
      dp3 = abs(p2[3] - 2*p1[3] + p0[3])
      dq3 = abs(q2[3] - 2*q1[3] + q0[3])

if (d < beta): apply filter
```

### Strong vs Normal Decision (§8.7.2.5.3)

For each 4-line group, additionally test:

```
strongFilter = (dp0 + dp3 < (beta + (beta >> 1)) >> 3)
            && (dq0 + dq3 < (beta + (beta >> 1)) >> 3)
            && (abs(p0[0] - q0[0]) < (5*tc + 1) >> 1)
```

### H.265 Normal Filter (§8.7.2.5.5)

Modifies p0, p1, q0, q1:

```
delta = Clip3(-tc, tc, (13*(q0 - p0) + 4*(q1 - p1) - 5*(q2 - p2) + 16) >> 5)
p0' = Clip1(p0 + delta)
q0' = Clip1(q0 - delta)
```

**p1 modification** (conditional on `dp < sideThreshold`):
```
deltap1 = Clip3(-(tc>>1), tc>>1, (((p2 + p0 + 1) >> 1) - p1 + delta) >> 1)
p1' = Clip1(p1 + deltap1)
```

### H.265 Strong Filter (§8.7.2.5.6)

Modifies p0, p1, p2, q0, q1, q2:

```
p0' = Clip3(p0 - 2*tc, p0 + 2*tc, (p2 + 2*p1 + 2*p0 + 2*q0 + q1 + 4) >> 3)
p1' = Clip3(p1 - 2*tc, p1 + 2*tc, (p2 + p1 + p0 + q0 + 2) >> 2)
p2' = Clip3(p2 - 2*tc, p2 + 2*tc, (2*p3 + 3*p2 + p1 + p0 + q0 + 4) >> 3)
```

**Note**: H.265 strong filter clips the change to `+/-2*tc` (bounded modification), unlike H.264 which clips to pixel range only.

## Hardware Implementation Notes

### Bs Computation Unit

| Input | Width | Source |
|-------|-------|--------|
| Prediction mode (p, q) | 2 bits each | Mode storage |
| MV (p, q) | 2 x 32 bits | MV storage |
| Reference index (p, q) | 2 x 4 bits | Ref idx storage |
| CBF (H.264 only) | 1 bit each | Residual flags |

**Latency**: 1 cycle (combinational priority encoder for Bs conditions).

### Filter Processing Order and Throughput

| Configuration | Edges per CTU (64x64) | Luma Samples Filtered |
|--------------|----------------------|----------------------|
| Vertical edges | 7 columns x 8 rows = 56 edges | Up to 56 x 4 = 224 lines |
| Horizontal edges | 8 columns x 7 rows = 56 edges | Up to 56 x 4 = 224 lines |
| **Total** | 112 edges | Up to 448 filter operations |

**Throughput target**: 1 edge (4 or 8 sample lines) per cycle for real-time 4K.

### Memory Access Pattern

```
Read:  p3 p2 p1 p0 | q0 q1 q2 q3  (8 samples per line, 4 lines = 32 samples)
Write: p2'p1'p0'   | q0'q1'q2'     (up to 6 modified samples per line)
```

**Line buffer**: Deblocking requires the above row's reconstructed samples. For 64x64 CTU at 4K (3840 pixels wide): above line buffer = 3840 x 4 lines x 1 byte = 15,360 bytes (luma).

### Filter Pipeline

| Stage | Operation | H.264 | H.265 |
|-------|-----------|-------|-------|
| 1 | Bs computation | 1 cycle | 1 cycle |
| 2 | Threshold lookup (alpha, beta, tc) | 1 cycle | 1 cycle |
| 3 | Filter decision (sample reads + condition) | 1 cycle | 1 cycle |
| 4 | Strong/normal selection | 1 cycle | 1 cycle |
| 5 | Filter computation + clipping | 1-2 cycles | 1-2 cycles |
| 6 | Write-back | 1 cycle | 1 cycle |
| **Total** | | **5-7 cycles/edge** | **5-7 cycles/edge** |
