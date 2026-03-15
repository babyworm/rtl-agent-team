# Quantization Matrices — H.264 & H.265

> References: H.264 §8.5.12.1, §8.5.12.2; H.265 §8.6.3

## Quantization Parameter (QP)

### QP-to-Qstep Relationship

Both H.264 and H.265 use a logarithmic QP scale: **QP +6 doubles the quantization step size**.

| QP | Relative Qstep | Approximate Qstep (H.264 4x4) |
|----|----------------|-------------------------------|
| 0 | 1.0x | 0.625 |
| 6 | 2.0x | 1.25 |
| 12 | 4.0x | 2.5 |
| 18 | 8.0x | 5.0 |
| 24 | 16.0x | 10.0 |
| 30 | 32.0x | 20.0 |
| 36 | 64.0x | 40.0 |
| 42 | 128.0x | 80.0 |
| 48 | 256.0x | 160.0 |
| 51 | 362.0x | 224.0 |

**QP range**: 0-51 for both H.264 and H.265 (with QP offset extensions in H.265 for > 8-bit).

### Chroma QP Mapping (§8.5.8 / §8.6.1)

Chroma QP is derived from luma QP via a non-linear mapping table:

| Luma QP | Chroma QPC (H.264) | Notes |
|---------|-------------------|-------|
| 0-29 | Same as luma | Linear region |
| 30 | 29 | Compression begins |
| 36 | 33 | |
| 42 | 36 | |
| 48 | 39 | |
| 51 | 39 | Maximum chroma QPC |

H.265 uses a similar table (Table 8-8) but allows per-component Cb/Cr QP offsets via PPS (`pps_cb_qp_offset`, `pps_cr_qp_offset`).

## H.264 Quantization (§8.5.12.1)

### Forward Quantization (Encoder)

```
level = sign(coeff) * ((abs(coeff) * MF[qp%6][i][j] + f) >> qbits)
```

| Parameter | Formula | Notes |
|-----------|---------|-------|
| `qbits` | `15 + floor(QP/6)` | Shift amount increases every 6 QP |
| `f` | `(1<<qbits)/3` (intra), `(1<<qbits)/6` (inter) | Rounding offset (dead-zone) |
| `MF[qp%6]` | Multiplication factor table | 6 sets of 3 unique values |

### MF (Multiplication Factor) Table

Three position classes in the 4x4 block due to transform normalization:

| Position | (0,0),(2,0),(0,2),(2,2) | (1,1),(1,3),(3,1),(3,3) | Others |
|----------|-------------------------|-------------------------|--------|
| Label | a^2 positions | b^2/4 positions | ab/2 positions |

| QP%6 | MF_a2 | MF_ab2 | MF_b4 |
|------|-------|--------|-------|
| 0 | 13107 | 5243 | 8066 |
| 1 | 11916 | 4660 | 7490 |
| 2 | 10082 | 4194 | 6554 |
| 3 | 9362 | 3647 | 5825 |
| 4 | 8192 | 3355 | 5243 |
| 5 | 7282 | 2893 | 4559 |

**Width**: MF values fit in 14 bits (max 13107).

### Inverse Quantization (Decoder-Mandated, §8.5.12.2)

```
coeff = (level * V[qp%6][i][j]) << floor(QP/6)
```

### V (Dequantization Scale) Table

| QP%6 | V_a2 | V_ab2 | V_b4 |
|------|------|-------|------|
| 0 | 10 | 16 | 13 |
| 1 | 11 | 18 | 14 |
| 2 | 13 | 20 | 16 |
| 3 | 14 | 23 | 18 |
| 4 | 16 | 25 | 20 |
| 5 | 18 | 29 | 23 |

**Width**: V values fit in 5 bits (max 29).

### Custom Scaling Matrices (High Profile)

H.264 High profile supports custom 4x4 and 8x8 scaling matrices signaled in SPS/PPS:

| Matrix | Size | Count | Usage |
|--------|------|-------|-------|
| 4x4 Intra Y | 4x4 = 16 entries | 1 | Intra luma 4x4 |
| 4x4 Intra Cb/Cr | 4x4 = 16 entries | 2 | Intra chroma |
| 4x4 Inter Y | 4x4 = 16 entries | 1 | Inter luma |
| 4x4 Inter Cb/Cr | 4x4 = 16 entries | 2 | Inter chroma |
| 8x8 Intra Y | 8x8 = 64 entries | 1 | Intra luma 8x8 |
| 8x8 Inter Y | 8x8 = 64 entries | 1 | Inter luma 8x8 |

**Total storage**: 6 * 16 + 2 * 64 = 224 entries * 8 bits = 224 bytes.

## H.265 Quantization (§8.6.3)

### Forward Quantization (Encoder)

```
level = sign(coeff) * ((abs(coeff) * quantCoeff + offset) >> shift)
```

| Parameter | Formula |
|-----------|---------|
| `shift` | `14 + floor(QP/6) + log2(nTbS) - (bitDepth + log2(nTbS) - 5)` simplified to `29 + floor(QP/6) - bitDepth - log2(nTbS)` |
| `offset` | `(1 << shift) / 3` (intra), `(1 << shift) / 6` (inter) |
| `quantCoeff` | `g_quantScales[QP%6] * scalingFactor[x][y] / 16` |

### g_quantScales Table

| QP%6 | g_quantScales | Bits |
|------|---------------|------|
| 0 | 26214 | 15 |
| 1 | 23302 | 15 |
| 2 | 20560 | 15 |
| 3 | 18396 | 15 |
| 4 | 16384 | 14 |
| 5 | 14564 | 14 |

### Inverse Quantization (§8.6.3, Decoder-Mandated)

```
d[x][y] = Clip3(-32768, 32767,
    ((coeff[x][y] * levelScale[QP%6] * scalingFactor[x][y] + offset) >> shift))
```

### levelScale Table (Inverse)

| QP%6 | levelScale |
|------|-----------|
| 0 | 40 |
| 1 | 45 |
| 2 | 51 |
| 3 | 57 |
| 4 | 64 |
| 5 | 72 |

**Width**: 7 bits (max 72).

### Scaling Lists (§7.3.4, §8.6.3)

H.265 supports scaling lists for all transform sizes:

| List ID | Size | Component | Type | Entries |
|---------|------|-----------|------|---------|
| 0 | 4x4 | Y Intra | Flat/Custom | 16 |
| 1 | 4x4 | Cb Intra | Flat/Custom | 16 |
| 2 | 4x4 | Cr Intra | Flat/Custom | 16 |
| 3 | 4x4 | Y Inter | Flat/Custom | 16 |
| 4 | 4x4 | Cb Inter | Flat/Custom | 16 |
| 5 | 4x4 | Cr Inter | Flat/Custom | 16 |
| 6-11 | 8x8 | Same as above | Flat/Custom | 64 |
| 12-17 | 16x16 | Same as above | Flat/Custom | 64 (subsampled from 16x16) |
| 18-19 | 32x32 | Y Intra/Inter | Flat/Custom | 64 (subsampled from 32x32) |

**Flat (default)**: All entries = 16.

**16x16 and 32x32 subsampling**: Only 8x8 = 64 unique scaling factors stored; each maps to a 2x2 (16x16) or 4x4 (32x32) region. Plus a separate DC coefficient scaling factor for 16x16 and 32x32.

**Total storage**: 6*16 + 6*64 + 6*64 + 2*64 = 96 + 384 + 384 + 128 = 992 entries * 8 bits = 992 bytes.

## Hardware Implementation Notes

### Quantizer Datapath

| Component | H.264 | H.265 |
|-----------|-------|-------|
| Multiplier width | 13-bit * 14-bit (MF) | 16-bit * 15-bit (quantCoeff) |
| Accumulator | 27-bit | 31-bit |
| Barrel shifter | 15-20 positions (qbits) | 14-24 positions (shift) |
| Dead-zone offset | Configurable (intra/inter) | Configurable |

### Dequantizer Datapath

| Component | H.264 | H.265 |
|-----------|-------|-------|
| Multiplier | 16-bit * 5-bit (V) | 16-bit * 7-bit (levelScale) |
| Scaling list multiply | 8-bit * result | 8-bit * result |
| Left-shift | 0-8 positions (QP/6) | 0-8 positions |
| Clip | 16-bit signed | 16-bit signed |

### Scaling List Storage

| Codec | SRAM Size | Access Pattern |
|-------|-----------|----------------|
| H.264 | 224 bytes | Indexed by [matrix_id][scan_position] |
| H.265 | 992 bytes | Indexed by [list_id][scan_position] |
| Both | Single-port sufficient | Read during (de)quantization, write on SPS/PPS parse |

### QP Control

| Signal | Width | Source |
|--------|-------|--------|
| slice_qp | 6 bits | Slice header |
| cu_qp_delta | 7 bits signed | CU-level delta (H.265) |
| mb_qp_delta | 7 bits signed | MB-level delta (H.264) |
| qp_Cb_offset | 5 bits signed | PPS |
| qp_Cr_offset | 5 bits signed | PPS (H.265 only) |
| effective_qp | 6 bits | `Clip3(0, 51, slice_qp + delta + offset)` |
