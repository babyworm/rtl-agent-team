# Butterfly Transform Operations — H.264 & H.265

> References: H.264 §8.5.12; H.265 §8.6.4.2

## H.264 4x4 Integer DCT (§8.5.12)

### Forward Transform (Encoder)

The H.264 4x4 transform is an integer approximation of DCT, avoiding floating-point mismatch.

**Core butterfly** (1-D, applied to rows then columns):

```
Stage 1 (butterfly):         Stage 2 (output):
  a = x[0] + x[3]             Y[0] =  a + b
  b = x[1] + x[2]             Y[1] =  2*c + d
  c = x[0] - x[3]             Y[2] =  a - b
  d = x[1] - x[2]             Y[3] =  c - 2*d
```

**Equivalent matrix**:
```
     | 1   1   1   1 |
Cf = | 2   1  -1  -2 | / (normalization deferred to quantization)
     | 1  -1  -1   1 |
     | 1  -2   2  -1 |
```

**Note**: The factor of 2 is implemented as a left-shift, not a multiply.

### Inverse Transform (§8.5.12.1, Decoder-Mandated)

```
Stage 1 (butterfly):         Stage 2 (output):
  e = x[0] + x[2]             z[0] = (e + f + 32) >> 6
  f = x[0] - x[2]             z[1] = (g + h + 32) >> 6
  g = e + (x[1] >> 1)  (*)    z[2] = (e - f + 32) >> 6  (*)
  h = f - (x[3] >> 1)  (*)    z[3] = (g - h + 32) >> 6  (*)
```

(*) Actual spec applies the butterfly differently — the `>>1` appears on specific coefficients to maintain integer precision:

```
  e = c[0] + c[2]
  f = c[0] - c[2]
  g = (c[1] >> 1) - c[3]
  h = c[1] + (c[3] >> 1)

  Y[0] = e + h
  Y[1] = f + g
  Y[2] = f - g
  Y[3] = e - h
```

The `>>6` shift is applied after both row and column passes (combined shift).

### Bit-Width Analysis (4x4 Forward)

| Stage | Input Width | Output Width | Operations |
|-------|-------------|-------------|------------|
| Input (residual) | 9-bit signed | — | cur - pred |
| Row butterfly stage 1 | 9-bit | 10-bit (add/sub) | 4 add/sub |
| Row butterfly stage 2 | 10-bit | 11-bit (2*c + d) | 2 add/sub, 1 shift |
| Column butterfly | 11-bit | 12-bit (add/sub) | Same structure |
| Column stage 2 | 12-bit | 13-bit | — |
| Post-scaling (MF * coeff) | 13-bit * 14-bit | 27-bit → 16-bit (shifted) | Multiply + shift |

### Hadamard Transform (DC Coefficients)

**4x4 Luma DC** (Intra16x16 mode):
```
Same butterfly as DCT but with all 1s and -1s:
H4 = | 1  1  1  1 |
     | 1  1 -1 -1 |
     | 1 -1 -1  1 |
     | 1 -1  1 -1 |
```
Applied to the 4x4 array of DC coefficients from 16 sub-blocks.

**2x2 Chroma DC**:
```
H2 = | 1  1 |
     | 1 -1 |
```

Both Hadamard transforms use only add/sub (no multiplies, no shifts in the core).

## H.265 DCT-II (§8.6.4.2)

### Transform Sizes

| Size | Matrix | Coefficient Width | Max Coeff Value |
|------|--------|-------------------|-----------------|
| 4x4 | 4x4 | 8-bit signed | 83 |
| 8x8 | 8x8 | 8-bit signed | 89 |
| 16x16 | 16x16 | 8-bit signed | 90 |
| 32x32 | 32x32 | 8-bit signed | 90 |

### 4x4 DCT-II Matrix

```
     | 64  64  64  64 |
T4 = | 83  36 -36 -83 |
     | 64 -64 -64  64 |
     | 36 -83  83 -36 |
```

### 8x8 DCT-II Matrix (Partial — Even/Odd Decomposition)

**Even rows** (reuse 4x4 structure):
```
E: | 64  64  64  64 |    (row 0)
   | 83  36 -36 -83 |    (row 2)
   | 64 -64 -64  64 |    (row 4)
   | 36 -83  83 -36 |    (row 6)
```

**Odd rows**:
```
O: | 89  75  50  18 |    (row 1)
   | 75 -18 -89 -50 |    (row 3)
   | 50 -89  18  75 |    (row 5)
   | 18 -50  75 -89 |    (row 7)
```

**Butterfly**: `Y[k] = E[k] + O[k]` for even k, `Y[k] = E[N-1-k] - O[N-1-k]` for odd k.

### 16x16 and 32x32

Follow the same even/odd recursive decomposition:
- 16x16: 8x8 even + 8 new odd coefficients {90, 87, 80, 70, 57, 43, 25, 9}
- 32x32: 16x16 even + 16 new odd coefficients {90, 90, 88, 85, 82, 78, 73, 67, 61, 54, 46, 38, 31, 22, 13, 4}

### Inverse Transform (§8.6.4.2)

Same matrix (DCT-II is self-transpose up to scaling), applied in reverse:

```
// First pass (columns):
shift1 = 7
intermediate[i][j] = (sum(T[k][i] * coeff[k][j], k=0..N-1) + (1 << (shift1-1))) >> shift1

// Second pass (rows):
shift2 = 20 - bitDepth
residual[i][j] = Clip3(-(1<<15), (1<<15)-1,
    (sum(T[k][j] * intermediate[i][k], k=0..N-1) + (1 << (shift2-1))) >> shift2)
```

### Accumulator Width per Transform Size

| Size | Input (after IQ) | After Multiply | After Accumulate | After Shift |
|------|------------------|----------------|-----------------|-------------|
| 4x4 | 16-bit signed | 24-bit (16+8) | 26-bit (+2 for 4 terms) | 19-bit (shift 7) |
| 8x8 | 16-bit signed | 24-bit | 27-bit (+3 for 8 terms) | 20-bit |
| 16x16 | 16-bit signed | 24-bit | 28-bit (+4 for 16 terms) | 21-bit |
| 32x32 | 16-bit signed | 24-bit | 29-bit (+5 for 32 terms) | 22-bit |

Second pass adds same growth; final shift brings result to `bitDepth + 1` bits.

## H.265 DST-VII (4x4 Intra Luma Only, §8.6.4.2)

### DST Matrix

```
       | 29  55  74  84 |
DST4 = | 74  74   0 -74 |
       | 84 -29 -74  55 |
       | 55 -84  74 -29 |
```

**When used**: 4x4 transform for intra-predicted luma blocks only. All other cases use DCT-II.

**Rationale**: DST-VII better matches the statistical distribution of intra residuals where energy concentrates away from the prediction boundary.

### DST vs DCT Coefficient Comparison

| Position | DST-VII | DCT-II | Notes |
|----------|---------|--------|-------|
| [0] | 29, 74, 84, 55 | 64, 83, 64, 36 | DST basis starts small (near boundary) |
| [3] | 84, -74, 55, -29 | 64, -36, -64, 83 | DST basis peaks in middle |

## Hardware Implementation Notes

### Butterfly Architecture (H.264 4x4)

| Resource | Count | Notes |
|----------|-------|-------|
| Adders | 8 per 1-D pass | 4 butterfly + 4 output |
| Shifts | 2 per 1-D pass | For the `2*x` terms |
| Multipliers | 0 | Pure add/shift design |
| Pipeline stages | 2 (row + column) | Can share single butterfly unit |
| Throughput | 1 block/8 cycles (time-shared) or 1 block/2 cycles (parallel) | |

### Partial Butterfly Architecture (H.265)

The even/odd decomposition enables hardware reuse:

| Transform Size | Unique Multiplications | With Butterfly Sharing |
|---------------|----------------------|----------------------|
| 4x4 | 16 (4x4 matrix) | 8 (even/odd split) |
| 8x8 | 64 | 24 (reuse 4x4 even + 16 odd) |
| 16x16 | 256 | 72 (reuse 8x8 even + 32 odd) |
| 32x32 | 1024 | 200 (reuse 16x16 even + 64 odd) |

### Shared Transform Unit

A single configurable unit handles all sizes:

```
Input Buffer (32 samples)
    |
    v
[Stage 1: 32-point odd butterfly] ← 16 multipliers
    |
[Stage 2: 16-point odd butterfly] ← 8 multipliers (reused from stage 1 subset)
    |
[Stage 3: 8-point odd butterfly]  ← 4 multipliers
    |
[Stage 4: 4-point even butterfly] ← 4 multipliers
    |
    v
Accumulate + Shift + Clip
    |
    v
Output Buffer (32 samples)
```

**Total multipliers**: 16 (8-bit x 16-bit) for full 32x32 support with time-multiplexing.

### Transpose Buffer

Between row and column passes, a transpose buffer is required:

| Transform Size | Buffer Size | Access Pattern |
|---------------|-------------|----------------|
| 4x4 | 16 x 16-bit = 32 bytes | Write row-major, read column-major |
| 8x8 | 64 x 16-bit = 128 bytes | Same |
| 16x16 | 256 x 16-bit = 512 bytes | Same |
| 32x32 | 1024 x 16-bit = 2 KB | Same |

Dual-port SRAM with separate read/write addresses enables concurrent row-write and column-read for pipeline overlap.
