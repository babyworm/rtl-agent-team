# Intra Prediction Modes — H.264 & H.265

> References: H.264 §8.3.1, H.265 §8.4.4

## H.264 Intra Prediction

### 4x4 Luma Modes (§8.3.1.1)

9 modes using up to 13 neighboring reconstructed samples (4 above, 4 left, 1 above-left, 4 above-right).

| Mode | Name | Direction | Reference Samples |
|------|------|-----------|-------------------|
| 0 | Vertical | Top→Down | A,B,C,D (above) |
| 1 | Horizontal | Left→Right | I,J,K,L (left) |
| 2 | DC | Average | All available neighbors |
| 3 | Diagonal Down-Left | 45° NE→SW | A,B,C,D,E,F,G,H (above+above-right) |
| 4 | Diagonal Down-Right | 45° NW→SE | All 13 samples |
| 5 | Vertical-Right | ~26.6° | M,A,B,C,D + I,J,K (above-left, above, left) |
| 6 | Horizontal-Down | ~26.6° | M,I,J,K,L + A,B,C (above-left, left, above) |
| 7 | Vertical-Left | ~26.6° | A,B,C,D,E,F,G (above+above-right) |
| 8 | Horizontal-Up | ~26.6° | I,J,K,L (left) |

**DC mode**: `(sum_above + sum_left + 4) >> 3` when both available; single-side + 2 >> 2 otherwise; 128 when neither.

### 16x16 Luma Modes (§8.3.1.2)

| Mode | Name | Description |
|------|------|-------------|
| 0 | Vertical | Copy 16 above samples to all rows |
| 1 | Horizontal | Copy 16 left samples to all columns |
| 2 | DC | Average of 32 boundary samples |
| 3 | Plane | Bilinear surface fit: `a + b*(x-7) + c*(y-7)` clipped to [0,255] |

**Plane mode coefficients** (§8.3.1.2, mode 3):
- `H = sum(x'=0..7) (x'+1) * (p[8+x',-1] - p[6-x',-1])`
- `V = sum(y'=0..7) (y'+1) * (p[-1,8+y'] - p[-1,6-y'])`
- `b = (5*H + 32) >> 6`, `c = (5*V + 32) >> 6`
- `a = 16 * (p[-1,15] + p[15,-1])`

### 8x8 Chroma Modes (§8.3.3)

| Mode | Name | Notes |
|------|------|-------|
| 0 | DC | Default mode |
| 1 | Horizontal | Left samples replicated |
| 2 | Vertical | Above samples replicated |
| 3 | Plane | Same formula as 16x16, scaled to 8x8 |

**Note**: Chroma mode numbering differs from luma 16x16 (DC=0, not DC=2).

## H.265 Intra Prediction (§8.4.4)

### 35 Modes for All Block Sizes (4x4 to 32x32)

| Mode | Name | intraPredAngle |
|------|------|----------------|
| 0 | Planar | N/A |
| 1 | DC | N/A |
| 2 | Angular (below-left) | 32 |
| 3 | Angular | 26 |
| 4 | Angular | 21 |
| 5 | Angular | 17 |
| 6 | Angular (diagonal) | 13 |
| 7 | Angular | 9 |
| 8 | Angular | 5 |
| 9 | Angular | 2 |
| 10 | Angular (horizontal) | 0 |
| 11 | Angular | -2 |
| 12 | Angular | -5 |
| 13 | Angular | -9 |
| 14 | Angular | -13 |
| 15 | Angular | -17 |
| 16 | Angular | -21 |
| 17 | Angular | -26 |
| 18 | Angular (diagonal) | -32 |
| 19 | Angular | -26 |
| 20 | Angular | -21 |
| 21 | Angular | -17 |
| 22 | Angular | -13 |
| 23 | Angular | -9 |
| 24 | Angular | -5 |
| 25 | Angular | -2 |
| 26 | Angular (vertical) | 0 |
| 27 | Angular | 2 |
| 28 | Angular | 5 |
| 29 | Angular | 9 |
| 30 | Angular | 13 |
| 31 | Angular | 17 |
| 32 | Angular | 21 |
| 33 | Angular | 26 |
| 34 | Angular (above-right) | 32 |

**intraPredAngle Table** (H.265 Table 8-4): Maps mode index to displacement per row/column.
Modes 2-17 use left reference array (column prediction), modes 18-34 use above reference array (row prediction).

### invAngle Table (§8.4.4.2.6)

For negative angles, projected reference samples from the opposite side are needed:

| intraPredAngle | -32 | -26 | -21 | -17 | -13 | -9 | -5 | -2 |
|----------------|-----|-----|-----|-----|-----|-----|-----|-----|
| invAngle | -256 | -315 | -390 | -482 | -630 | -910 | -1638 | -4096 |

`invAngle = -256 * 256 / intraPredAngle` (rounded).

### Planar Mode (§8.4.4.2.4)

Linear interpolation in both horizontal and vertical directions:

```
predSamples[x][y] = ((nTbS - 1 - x) * p[-1][y] + (x + 1) * p[nTbS][-1]
                    + (nTbS - 1 - y) * p[x][-1] + (y + 1) * p[-1][nTbS]
                    + nTbS) >> (log2(nTbS) + 1)
```

- Requires: top-right corner sample `p[nTbS][-1]` and bottom-left corner `p[-1][nTbS]`
- Intermediate precision: input bit_depth + log2(nTbS) + 1 bits

### DC Mode (§8.4.4.2.5)

`dcVal = (sum(p[x][-1], x=0..nTbS-1) + sum(p[-1][y], y=0..nTbS-1) + nTbS) >> (log2(nTbS) + 1)`

**DC filtering** (applied only for 4x4): top-left corner and first row/column samples are filtered with adjacent reference samples.

### Reference Sample Filtering (§8.4.4.2.3)

Mode-dependent filtering of reference samples before prediction:

| Block Size | Modes Using Filtered References |
|------------|--------------------------------|
| 4x4 | DC only (mode 1) — no filtering for angular |
| 8x8 | Modes 2-8, 12-16, 20-24, 28-34 (near-horizontal/vertical filtered) |
| 16x16 | Modes 2-8, 12-16, 20-24, 28-34 |
| 32x32 | All angular modes + strong intra smoothing |

**Strong intra smoothing** (32x32 only, §8.4.4.2.3): When `abs(p[-1][0] + p[63][-1] - 2*p[-1][-1]) < threshold` AND `abs(p[-1][0] + p[-1][63] - 2*p[-1][-1]) < threshold`, apply 2-point interpolation using only corner reference samples.
Threshold: `1 << (bitDepth - 5)`.

## Hardware Implementation Notes

| Parameter | H.264 | H.265 |
|-----------|-------|-------|
| Max reference samples per block | 13 (4x4) / 33 (16x16) | 2*nTbS + 1 (up to 65 for 32x32) |
| Prediction arithmetic | 8-bit add/shift | bitDepth-bit add/shift + interpolation |
| Pipeline stages (typical) | 1 (simple directional copy) | 2-3 (filtering + angular interpolation) |
| Reference buffer (line buffer) | 1 row of MBs (16 samples/MB) | 1 row of CTUs (up to 64 samples/CTU) |
| Throughput target | 1 mode/cycle (4x4) | 1 row/cycle (angular), 1 sample/cycle (planar) |

**Critical path**: Angular prediction with negative angle requires projected sample fetch from opposite reference array, adding 1 cycle latency for address computation.
