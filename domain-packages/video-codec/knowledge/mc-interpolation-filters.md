# Motion Compensation Interpolation Filters — H.264 & H.265

> References: H.264 §8.4.2.2.1; H.265 §8.5.3.3.3, Tables 8-2, 8-3

## H.264 Luma Interpolation (§8.4.2.2.1)

### Half-Pel: 6-Tap FIR Filter

Coefficients: **{1, -5, 20, 20, -5, 1}**, normalization: `/32`

Integer-pel positions labeled `A`..`P`, half-pel positions labeled `a`..`s`:

```
  A  aa  B
  cc dd  ee
  C  bb  D
```

**Horizontal half-pel** (e.g., position `b`):
`b = Clip1((A - 5*C + 20*D + 20*E - 5*F + G + 16) >> 5)`

**Vertical half-pel** (e.g., position `h`):
`h = Clip1((A - 5*C + 20*G + 20*M - 5*R + T + 16) >> 5)`

**Diagonal half-pel** (e.g., position `j`):
Apply 6-tap horizontally on vertically-interpolated half-pel samples (2-pass):
1. Compute vertical half-pel intermediates without rounding (keep full precision)
2. Apply horizontal 6-tap on these intermediates
3. `j = Clip1((cc - 5*dd + 20*h1 + 20*m1 - 5*ee + ff + 512) >> 10)`

### Quarter-Pel: Bilinear Average

| Position | Formula |
|----------|---------|
| `a` (between A and b) | `a = (A + b + 1) >> 1` |
| `c` (between A and h) | `c = (A + h + 1) >> 1` |
| `d` (between b and h) | `d = (b + h + 1) >> 1` (diagonal quarter-pel uses half-pel results) |
| `e` (between b and B) | `e = (b + B + 1) >> 1` |

All quarter-pel positions are simple averages of an integer-pel and a half-pel, or two half-pel positions.

### H.264 Chroma Interpolation (§8.4.2.2.2)

Eighth-pel precision (3 fractional bits for MV), bilinear interpolation:

```
pred = ((8-dx)*(8-dy)*A + dx*(8-dy)*B + (8-dx)*dy*C + dx*dy*D + 32) >> 6
```

where `dx = mvx & 7`, `dy = mvy & 7`, and A/B/C/D are the four surrounding integer samples.

### H.264 Precision Summary

| Stage | Input Width | Intermediate Width | Output Width | Rounding |
|-------|-------------|-------------------|-------------|----------|
| 6-tap horizontal | 8-bit unsigned | 16-bit signed | — | No rounding (pass to vertical) |
| 6-tap vertical (on pixels) | 8-bit unsigned | 16-bit signed | 8-bit (clipped) | `+16, >>5` |
| 6-tap vertical (on intermediates) | 16-bit signed | 21-bit signed | 8-bit (clipped) | `+512, >>10` |
| Quarter-pel average | 8-bit unsigned | 9-bit unsigned | 8-bit (clipped) | `+1, >>1` |
| Chroma bilinear | 8-bit unsigned | 14-bit unsigned | 8-bit (clipped) | `+32, >>6` |

## H.265 Luma Interpolation (§8.5.3.3.3.1)

### 8-Tap Filter (Table 8-2)

| Fractional Position | f[0] | f[1] | f[2] | f[3] | f[4] | f[5] | f[6] | f[7] |
|---------------------|------|------|------|------|------|------|------|------|
| 1/4 | -1 | 4 | -10 | 58 | 17 | -5 | 1 | 0 |
| 1/2 | -1 | 4 | -11 | 40 | 40 | -11 | 4 | -1 |
| 3/4 | 0 | 1 | -5 | 17 | 58 | -10 | 4 | -1 |

**Coefficient sum**: Always 64 (normalization by `>>6`).

**Symmetry**: 1/4-pel and 3/4-pel are mirrored. Half-pel is symmetric.

**Filter application**:
```
predSample = (sum(f[k] * ref[x + k - 3], k=0..7) + offset) >> shift
```

- First pass (horizontal): `shift = Min(4, bitDepth - 8)`, `offset = 0` if shift=0, else `1 << (shift-1)`
- Second pass (vertical): `shift = 6 + (bitDepth - 8) - Min(4, bitDepth - 8)`, `offset = 1 << (shift-1)`
- Single pass (1-D): `shift = 6`, `offset = 32`

### H.265 Chroma Interpolation (§8.5.3.3.3.2)

4-tap filter (Table 8-3), eighth-pel precision:

| Fractional Position | f[0] | f[1] | f[2] | f[3] |
|---------------------|------|------|------|------|
| 1/8 | -2 | 58 | 10 | -2 |
| 2/8 | -4 | 54 | 16 | -2 |
| 3/8 | -6 | 46 | 28 | -4 |
| 4/8 | -4 | 36 | 36 | -4 |
| 5/8 | -4 | 28 | 46 | -6 |
| 6/8 | -2 | 16 | 54 | -4 |
| 7/8 | -2 | 10 | 58 | -2 |

**Coefficient sum**: Always 64.

### H.265 Precision Summary

| Stage | Input Width | Intermediate Width | Output Width | Shift |
|-------|-------------|-------------------|-------------|-------|
| Luma 8-tap horizontal (8-bit) | 8-bit | 15-bit signed | (intermediate) | shift1 = 0 |
| Luma 8-tap vertical (8-bit) | 15-bit signed | 22-bit signed | 8-bit (clipped) | shift2 = 6 |
| Luma 8-tap horizontal (10-bit) | 10-bit | 16-bit signed | (intermediate) | shift1 = 2 |
| Luma 8-tap vertical (10-bit) | 16-bit signed | 22-bit signed | 10-bit (clipped) | shift2 = 4 |
| Chroma 4-tap 1-D | 8-bit | 14-bit signed | 8-bit (clipped) | 6 |
| Chroma 4-tap 2-D pass1 | 8-bit | 15-bit signed | (intermediate) | 0 (8-bit) |
| Chroma 4-tap 2-D pass2 | 15-bit signed | 22-bit signed | 8-bit (clipped) | 6 |

## Accumulator Width Derivation

### General Formula

For an N-tap filter with maximum coefficient magnitude `C_max` applied to `B`-bit input:

```
intermediate_width = B + ceil(log2(N * C_max))
```

### H.264 6-Tap Luma

- Max positive sum: `20 + 20 = 40` (coeff * max_pixel = 40 * 255 = 10,200)
- Max negative sum: `|-5| + |-5| + 1 + 1 = 12` (12 * 255 = 3,060)
- Worst case: `10,200 + 3,060 = 13,260` → needs 14 bits unsigned → 15 bits signed
- Two-pass diagonal: 15 + 6 = 21 bits signed intermediate

### H.265 8-Tap Luma

- Max coefficient magnitude: 58 (at 1/4-pel)
- Worst case sum of abs coefficients: `1 + 4 + 10 + 58 + 17 + 5 + 1 + 0 = 96`
- 8-bit input: `8 + ceil(log2(96))` = `8 + 7` = 15 bits signed (single pass)
- Two-pass: first pass outputs ~15 bits, second pass: `15 + 7` = 22 bits signed

## Hardware Implementation Notes

### Filter Architecture Comparison

| Property | H.264 6-Tap | H.265 8-Tap | H.265 4-Tap Chroma |
|----------|-------------|-------------|-------------------|
| Multipliers per tap | 6 (or shift-add) | 8 | 4 |
| Coefficients fixed? | Yes (1 set) | Yes (3 sets) | Yes (7 sets) |
| Shift-add possible | Yes ({1,-5,20} → shifts) | Partial (58 = 64-4-2) | Partial |
| Pipeline stages (typ.) | 2 (multiply + accumulate) | 2-3 | 2 |
| Parallelism | 4 or 8 samples/cycle | 4 or 8 samples/cycle | 4 samples/cycle |

### H.264 Shift-Add Decomposition

| Coefficient | Decomposition | Operations |
|-------------|---------------|------------|
| 1 | identity | 0 |
| -5 | -(4 + 1) = -(x<<2 + x) | 1 shift, 1 add, 1 negate |
| 20 | 16 + 4 = x<<4 + x<<2 | 2 shifts, 1 add |

Total per tap position: 6 add/sub operations (no multiplier needed).

### Memory Bandwidth

| Codec | Block Size | Filter Taps | Samples Needed | Bytes (8-bit) |
|-------|-----------|-------------|----------------|---------------|
| H.264 | 16x16 luma | 6 (each dim) | 21 x 21 | 441 |
| H.264 | 8x8 chroma | bilinear | 9 x 9 | 81 |
| H.265 | 64x64 luma | 8 (each dim) | 71 x 71 | 5,041 |
| H.265 | 32x32 chroma | 4 (each dim) | 35 x 35 | 1,225 |

**Bandwidth reduction**: Reference data cache (8-16 KB typical) exploits spatial locality between adjacent PUs within the same CTU.
