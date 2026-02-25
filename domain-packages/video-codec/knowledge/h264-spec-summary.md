# H.264/AVC Specification Summary

> Reference: ITU-T H.264 (V14) / ISO/IEC 14496-10

## Core Coding Tools

### Intra Prediction (§8.3.1)
- **4x4 Luma**: 9 modes (Vertical, Horizontal, DC, Diagonal Down-Left, Diagonal Down-Right, Vertical-Right, Horizontal-Down, Vertical-Left, Horizontal-Up)
- **16x16 Luma**: 4 modes (Vertical, Horizontal, DC, Plane)
- **8x8 Chroma**: 4 modes (DC, Horizontal, Vertical, Plane)
- Prediction uses reconstructed neighboring samples (above, left, above-left, above-right)
- Unavailable neighbors: substitute with DC value (128 for 8-bit)

### Inter Prediction (§8.4)
- Block sizes: 16x16, 16x8, 8x16, 8x8, 8x4, 4x8, 4x4
- Quarter-pixel motion vectors (6-tap FIR filter for half-pel, bilinear for quarter-pel)
- Multiple reference frames (max 16 for P-slices, 32 for B-slices)
- Weighted prediction for fade compensation

### Transform & Quantization (§8.5)
- 4x4 integer DCT (approximation of DCT, exact inverse)
- Hadamard transform for DC coefficients (4x4 luma, 2x2 chroma)
- Quantization: 52 QP levels (QP 0-51), 6 QP = 2x step size
- Scaling lists for custom quantization matrices

### Entropy Coding (§9)
- CAVLC (Context-Adaptive Variable-Length Coding): baseline profile
- CABAC (Context-Adaptive Binary Arithmetic Coding): main/high profile
  - Binary arithmetic coder with probability estimation
  - Context models: ~400 contexts
  - Bypass mode for equiprobable bins

### Deblocking Filter (§8.7)
- Applied at 4x4 block boundaries
- Boundary strength (Bs): 0-4 based on coding mode and MVs
- Adaptive filter strength based on QP and Bs
- Can be disabled per slice

## Key Data Structures

| Structure | Description | Size (4K) |
|-----------|-------------|-----------|
| Reference Frame | Decoded picture buffer | ~12 MB (YUV420, 8-bit) |
| MB Info | Mode, MV, QP per macroblock | ~1 MB |
| Deblocking BS | Boundary strength per edge | ~256 KB |
| CABAC Context | Probability states | ~1.6 KB |

## JM Reference Software Function Map

| H.264 Section | JM Function | Description |
|---------------|-------------|-------------|
| §8.3.1.1 | `Intra4x4_pred()` | 4x4 intra prediction |
| §8.3.1.2 | `Intra16x16_pred()` | 16x16 intra prediction |
| §8.4.1 | `LumaPrediction()` | Inter prediction |
| §8.5.12 | `forward_4x4()` | Forward 4x4 transform |
| §8.5.12 | `inverse_4x4()` | Inverse 4x4 transform |
| §9.3 | `arienco_start_encoding()` | CABAC encoding start |
| §8.7 | `DeblockFrame()` | Deblocking filter |
