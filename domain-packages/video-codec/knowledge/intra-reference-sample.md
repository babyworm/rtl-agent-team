# Intra Reference Sample Availability & Substitution

> References: H.264 §8.3.1, §8.3.1.2.1; H.265 §8.4.4.2.2

## H.264 Reference Sample Availability (§8.3.1)

### Neighboring Sample Layout (4x4 Block)

```
  M  A  B  C  D  E  F  G  H
  I [             ]
  J [   4x4 block ]
  K [             ]
  L [             ]
```

- `A-D`: above (p[x,-1], x=0..3)
- `E-H`: above-right (p[x,-1], x=4..7)
- `I-L`: left (p[-1,y], y=0..3)
- `M`: above-left (p[-1,-1])

### Availability Conditions (§6.4.1, §8.3.1)

A neighbor is **unavailable** when any of the following hold:

| Condition | Affected Samples | Notes |
|-----------|-----------------|-------|
| Top picture boundary | A-H, M | First MB row |
| Left picture boundary | I-L, M | First MB column |
| Slice boundary (different slice) | Any neighbor in other slice | Unless constrained_intra_pred_flag=0 |
| Inter-coded neighbor + constrained_intra_pred | Any neighbor in inter MB | When constrained_intra_pred_flag=1 |
| Above-right beyond MB boundary | E-H | Right-most 4x4 in MB, or neighbor MB unavailable |

**Above-right availability for 4x4 sub-blocks within a macroblock**:
- Sub-blocks 0,1,4,5 in raster order: above-right is the adjacent 4x4 within the MB
- Sub-blocks 3,7,11,13,15: above-right is NEVER available (falls outside current MB or is below-right)

### Substitution Rules (§8.3.1.1)

When neighbors are unavailable, substitute in this order:

1. If **all** neighbors unavailable: fill with `1 << (bitDepth - 1)` (128 for 8-bit)
2. Otherwise, substitute unavailable samples with the nearest available sample by scanning:
   - Scan order: left-bottom → left-top → above-left → above-left → above-right
   - `p[x,-1]` unavailable: copy from nearest available in scan

**16x16 mode**: If above or left row entirely unavailable, only DC mode (mode 2) uses partial data. Vertical requires above; Horizontal requires left; Plane requires both.

### Constrained Intra Prediction (§7.4.5, constrained_intra_pred_flag)

| Flag | Effect | Use Case |
|------|--------|----------|
| 0 | Any reconstructed neighbor used | Normal operation |
| 1 | Only intra-coded neighbors used | Error resilience, parallel decoding |

When `constrained_intra_pred_flag=1`, inter-coded neighbors are treated as unavailable. This enables independent slice decoding since intra prediction does not depend on inter reconstruction results.

**Hardware impact**: Requires per-neighbor mode check (intra vs inter) before reference sample fetch, adding logic to the availability checker.

## H.265 Reference Sample Processing (§8.4.4.2.2)

### Reference Sample Array

H.265 uses a unified 1-D reference array of size `4*nTbS + 1`:

```
  p[-1][2N-1]
      ...
  p[-1][0]
  p[-1][-1]  p[0][-1]  p[1][-1]  ...  p[2N-1][-1]
```

Total samples: `2*nTbS + 1` above (including corner) + `2*nTbS` left = `4*nTbS + 1`.

### Availability Check (§8.4.4.2.2, Step 1)

For each reference sample position, availability depends on:

| Check | Condition |
|-------|-----------|
| Picture boundary | Sample position outside picture bounds |
| CTU boundary | Sample in different CTU row (for above-right extension) |
| Slice boundary | Sample in different slice |
| Tile boundary | Sample in different tile |
| CU availability | Neighboring CU not yet reconstructed (Z-scan order) |
| Constrained intra | `constrained_intra_pred_flag=1` AND neighbor is inter-coded |

### Substitution (§8.4.4.2.2, Step 2)

Process the `4*nTbS + 1` samples in a specific scan order:

1. **Scan**: Start from bottom-left `p[-1][2*nTbS-1]`, scan upward to `p[-1][0]`, then `p[-1][-1]`, then right to `p[2*nTbS-1][-1]`
2. **First available**: Find the first available sample in scan order
3. **Fill unavailable**: Replace each unavailable sample with the nearest available sample found so far in scan order
4. **All unavailable**: If no sample is available, fill entire array with `1 << (bitDepth - 1)`

### Reference Sample Filtering (§8.4.4.2.3, Step 3)

After substitution, optionally apply a 3-tap [1,2,1]/4 smoothing filter:

`p'[i] = (p[i-1] + 2*p[i] + p[i+1] + 2) >> 2`

Corner sample: `p'[-1][-1] = (p[-1][0] + 2*p[-1][-1] + p[0][-1] + 2) >> 2`

**Filter decision** — based on `filterFlag` from Table 8-3 (intraHorFilterType/intraVerFilterType):

| Condition | filterFlag |
|-----------|------------|
| nTbS = 4 AND mode = DC | 1 |
| nTbS = 4 AND angular mode | 0 |
| nTbS >= 8 AND near-diagonal mode | 0 |
| nTbS >= 8 AND near-horiz/vert mode | 1 |
| nTbS = 32 AND strong smoothing applicable | Use bilinear (see below) |

### Strong Intra Smoothing (§8.4.4.2.3, 32x32 only)

Replaces 3-tap filter with bilinear interpolation using only 4 corner samples:

**Condition**: `bilinearLeft + bilinearAbove < threshold`
- `bilinearLeft = abs(p[-1][0] + p[-1][63] - 2*p[-1][31])`
- `bilinearAbove = abs(p[0][-1] + p[63][-1] - 2*p[31][-1])`
- `threshold = 1 << (bitDepth - 5)` (= 8 for 8-bit)

**Bilinear formula** (above reference):
`p'[x][-1] = ((63-x) * p[0][-1] + (x+1) * p[63][-1] + 32) >> 6` for x = 0..62

**Bilinear formula** (left reference):
`p'[-1][y] = ((63-y) * p[-1][0] + (y+1) * p[-1][63] + 32) >> 6` for y = 0..62

## Hardware Implementation Notes

### Reference Buffer Architecture

| Component | Size (32x32, 8-bit) | Purpose |
|-----------|---------------------|---------|
| Above line buffer | 64 samples = 64 bytes | Stores above + above-right references |
| Left column buffer | 64 samples = 64 bytes | Stores left + below-left references |
| Corner register | 1 sample = 1 byte | Stores above-left corner |
| Filtered copy | 129 samples = 129 bytes | Post-filter reference array |

### Availability Checker

| Input | Width | Source |
|-------|-------|--------|
| CU position (x, y) | 2 * log2(max_CTU_size) bits | CU decoder |
| Slice/tile boundary flags | 4 bits (above, left, above-right, below-left) | Slice header parser |
| Neighbor coding mode | 1 bit per neighbor CU | Mode storage |
| constrained_intra_pred_flag | 1 bit | PPS |

**Latency**: Availability check + substitution can be pipelined in 2 cycles:
1. Cycle 1: Parallel availability check for all `4*nTbS + 1` positions
2. Cycle 2: Priority-encoder scan + substitution fill

### Critical Timing Paths

- **Substitution scan**: Sequential dependency across `4*nTbS + 1` samples. For 32x32 (129 samples), use carry-chain or tree-based nearest-available propagation to avoid 129-deep combinational path.
- **Filter decision**: Depends on mode + block size — available 1 cycle after mode decode, before reference fetch completes.
- **Strong smoothing condition**: Requires 4 samples (corners) and 2 midpoint samples — check can begin as soon as substitution completes for those 6 positions.
