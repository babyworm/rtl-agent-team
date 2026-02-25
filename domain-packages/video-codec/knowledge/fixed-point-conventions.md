# Fixed-Point Arithmetic Conventions for H.264/H.265

## General Notation

`Q(m.f)` — m integer bits, f fractional bits, total width = m + f (+ 1 sign bit if signed).

Example: `Q(1.14)` signed = 1 sign + 1 integer + 14 fractional = 16 bits total.

## H.264 Transform & Quantization

### Forward Integer DCT (4x4)

H.264 uses an integer-approximate DCT to avoid mismatch between encoder and decoder.

| Operation | Input Width | Output Width | Notes |
|-----------|-----------|-------------|-------|
| Forward DCT (core) | 9-bit signed (residual) | 16-bit signed | Butterfly: add/sub + shift |
| Hadamard (DC, 4x4) | 16-bit signed | 16-bit signed | No additional growth |
| Post-scaling | 16-bit signed | 16-bit signed | Multiply by MF table, right-shift by qbits |

**MF (Multiplication Factor) table values** (per QP%6):

| QP%6 | MF[0,0] | MF[0,2] | MF[2,2] |
|------|---------|---------|---------|
| 0 | 13107 | 5243 | 8066 |
| 1 | 11916 | 4660 | 7490 |
| 2 | 10082 | 4194 | 6554 |
| 3 | 9362 | 3647 | 5825 |
| 4 | 8192 | 3355 | 5243 |
| 5 | 7282 | 2893 | 4559 |

**qbits** = 15 + floor(QP/6)

### Inverse Quantization + IDCT

| Operation | Input Width | Output Width | Notes |
|-----------|-----------|-------------|-------|
| Inverse quant | 16-bit signed | 16-bit signed | Multiply by V table, left-shift by floor(QP/6) |
| Inverse DCT (core) | 16-bit signed | 10-bit signed (clipped) | Butterfly + round + right-shift 6 |
| Reconstruction | 10-bit signed + 8-bit pred | 8-bit unsigned (clip 0-255) | Saturating add + clip |

### Sub-Pixel Interpolation (Motion Compensation)

| Precision | Filter Taps | Coefficient Sum | Intermediate Width |
|-----------|------------|----------------|-------------------|
| Half-pel (6-tap) | {1, -5, 20, 20, -5, 1} | 32 | 8-bit input → 16-bit intermediate |
| Quarter-pel | Average of integer and half-pel | — | 16-bit → 8-bit (round + clip) |

**Rounding**: `(sum + 16) >> 5` for half-pel, `(a + b + 1) >> 1` for quarter-pel.

## H.265 Transform & Quantization

### Forward DCT-II (4x4, 8x8, 16x16, 32x32)

H.265 uses matrix multiplication with fixed 16-bit signed coefficients.

| Transform Size | Matrix Dimensions | Coefficient Width | Output Growth |
|---------------|------------------|------------------|--------------|
| 4x4 | 4x4 | 8-bit (max: 83) | +10 bits from input |
| 8x8 | 8x8 | 8-bit (max: 89) | +11 bits from input |
| 16x16 | 16x16 | 8-bit (max: 90) | +12 bits from input |
| 32x32 | 32x32 | 8-bit (max: 90) | +13 bits from input |

**Shift after transform**: `shift = log2(N) + bitdepth + 1 - 15` (first pass), adjusted for second pass.

### DST (4x4, Intra Luma Only)

| Coefficient set | {29, 55, 74, 84} |
|----------------|-------------------|
| Max intermediate | 9-bit input × 84 → 16-bit |

### Quantization

| Parameter | Formula | Width |
|-----------|---------|-------|
| `level` | `sign(coeff) × ((abs(coeff) × quant_coeff + offset) >> shift)` | 16-bit signed |
| `quant_coeff` | From scaling list × `g_quantScales[qp%6]` | 16-bit |
| `g_quantScales` | {26214, 23302, 20560, 18396, 16384, 14564} | 15-bit |
| `shift` | `14 + qp/6 - bitdepth - log2(N)` | — |

### SAO (Sample Adaptive Offset)

| Operation | Input | Offset Range | Output |
|-----------|-------|-------------|--------|
| Edge offset | reconstructed sample | -7 to +7 (3-bit signed) | clip to [0, (1<<bitdepth)-1] |
| Band offset | reconstructed sample | -7 to +7 (3-bit signed) | clip to [0, (1<<bitdepth)-1] |

## Implementation Guidelines

### Bit-Width Sizing Rules

1. **Multiply**: output_width = a_width + b_width
2. **Add N values**: output_width = max(a_width, b_width) + ceil(log2(N))
3. **Right-shift with rounding**: add `1 << (shift-1)` before shifting; output_width = input_width - shift
4. **Clipping**: output must saturate, not wrap — use `assign o_data = (tmp > MAX) ? MAX : (tmp < MIN) ? MIN : tmp[W-1:0];`

### Common Pitfall: Sign Extension

Always sign-extend before arithmetic:
```systemverilog
// CORRECT: sign-extend 9-bit to 16-bit before multiply
logic signed [15:0] extended = {{7{input_9b[8]}}, input_9b};
logic signed [31:0] product = extended * coefficient;

// WRONG: multiply without extension (implicit zero-extend for unsigned)
logic [31:0] product = input_9b * coefficient;  // BUG if input_9b is signed
```
