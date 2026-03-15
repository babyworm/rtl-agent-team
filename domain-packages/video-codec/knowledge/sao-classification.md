# SAO (Sample Adaptive Offset) Classification — H.265

> Reference: H.265 §8.7.3

## Overview

SAO is an in-loop filter applied after deblocking in H.265. It classifies reconstructed samples and applies per-class offsets to reduce ringing and banding artifacts.

| Property | Value |
|----------|-------|
| Scope | Per-CTB (independently per luma/Cb/Cr) |
| Types | Edge Offset (EO) + Band Offset (BO) |
| Signaled | sao_type_idx (0=off, 1-4=EO, 5=BO) per component per CTB |
| Merge modes | Left CTB merge, above CTB merge |
| Offset range | -7 to +7 (4-bit signed, but only 3-bit magnitude) |

## Edge Offset (EO) — sao_type_idx 1-4

### Edge Classes (§8.7.3.1)

Each EO type defines a direction for comparing the center sample `c` with two neighbors `a` and `b`:

| sao_type_idx | EO Class | Direction | Neighbor a | Neighbor b |
|-------------|----------|-----------|------------|------------|
| 1 | EO_0 | Horizontal | c[-1, 0] | c[+1, 0] |
| 2 | EO_1 | Vertical | c[0, -1] | c[0, +1] |
| 3 | EO_2 | 135-degree | c[-1, -1] | c[+1, +1] |
| 4 | EO_3 | 45-degree | c[+1, -1] | c[-1, +1] |

### Category Derivation (§8.7.3.1, Table 8-9)

For each sample, compare `c` with neighbors `a` and `b`:

| Category | Condition | Interpretation | Typical Offset |
|----------|-----------|---------------|---------------|
| 0 | None of below | Monotone region | 0 (not offset) |
| 1 | `c < a` AND `c < b` | Local valley | Positive (+1 to +7) |
| 2 | `(c < a AND c == b)` OR `(c == a AND c < b)` | Partial valley | Positive (+1 to +7) |
| 3 | `(c > a AND c == b)` OR `(c == a AND c > b)` | Partial peak | Negative (-1 to -7) |
| 4 | `c > a` AND `c > b` | Local peak | Negative (-1 to -7) |

**Category 0**: No offset applied (smooth or non-edge region). Category 0 offset is always 0 and not signaled.

**Sign constraint**: Categories 1 and 2 always receive positive offsets; categories 3 and 4 always receive negative offsets. Only the magnitude (1-7) is signaled.

### EO Classification Logic

```
edgeIdx = 2 + Sign(c - a) + Sign(c - b)
where Sign(x) = (x > 0) ? 1 : (x < 0) ? -1 : 0
```

| Sign(c-a) | Sign(c-b) | edgeIdx | Category |
|-----------|-----------|---------|----------|
| -1 | -1 | 0 | 1 (valley) |
| -1 | 0 | 1 | 2 (partial valley) |
| 0 | -1 | 1 | 2 (partial valley) |
| 0 | 0 | 2 | 0 (flat) |
| 1 | 0 | 3 | 3 (partial peak) |
| 0 | 1 | 3 | 3 (partial peak) |
| 1 | 1 | 4 | 4 (peak) |
| -1 | 1 | 2 | 0 (flat) |
| 1 | -1 | 2 | 0 (flat) |

**Note**: `Sign(c-a)=-1, Sign(c-b)=+1` (and vice versa) maps to category 0 (no offset) since it represents a monotone gradient, not an edge.

## Band Offset (BO) — sao_type_idx 5

### Band Classification (§8.7.3.2)

Sample values are divided into 32 bands based on the 5 MSBs:

```
bandIdx = sample >> (bitDepth - 5)
```

| bitDepth | Band Width | Band Range Example (band 0) | Band Range (band 16) |
|----------|-----------|---------------------------|---------------------|
| 8 | 8 | 0-7 | 128-135 |
| 10 | 32 | 0-31 | 512-543 |

### Band Position and Active Bands

Only **4 consecutive bands** are active (offset-applied) per CTB:

| Parameter | Description |
|-----------|-------------|
| `sao_band_position` | Starting band index (0-28), 5 bits |
| Active bands | `sao_band_position` to `sao_band_position + 3` |
| Offsets | 4 signed values, one per active band |

**Offset range**: -7 to +7 for each of the 4 active bands (no sign constraint unlike EO).

**Rationale**: Banding artifacts concentrate in smooth gradients where sample values cluster in a few adjacent bands. The 4-band window targets these clusters.

### BO Classification Logic

```
bandIdx = sample >> (bitDepth - 5)
if (bandIdx >= sao_band_position AND bandIdx <= sao_band_position + 3):
    offset = sao_offset[bandIdx - sao_band_position]
else:
    offset = 0
```

## SAO Merge Modes (§7.3.8.3)

### Left Merge (sao_merge_left_flag)

Copy all SAO parameters (type, offsets, band position) from the left CTB.

### Above Merge (sao_merge_up_flag)

Copy all SAO parameters from the above CTB.

**Merge priority**: Left merge checked first. If set, above merge is not signaled. Both reduce syntax overhead for uniform regions.

### Parameter Storage per CTB

| Parameter | Width | Per Component |
|-----------|-------|---------------|
| sao_type_idx | 3 bits | Yes (Y, Cb, Cr) |
| sao_offset[0..3] | 4 x 4 bits = 16 bits | Yes |
| sao_band_position (BO only) | 5 bits | Yes |
| sao_eo_class (EO only) | 2 bits | Yes |
| **Total per CTB** | ~24 bits per component | 72 bits (3 components) |

## Offset Application

### Formula

```
reconSample' = Clip3(0, (1 << bitDepth) - 1, reconSample + offset)
```

**Offset scaling** for high bit depth (§8.7.3):
- Offsets are left-shifted by `(bitDepth - 8)` when `bitDepth > 8`
- Signaled values are always in 8-bit-equivalent range (-7 to +7)
- Effective offset for 10-bit: -28 to +28

## Hardware Implementation Notes

### EO Classifier

| Input | Width | Notes |
|-------|-------|-------|
| Center sample (c) | bitDepth bits | Current reconstructed sample |
| Neighbor a | bitDepth bits | Direction-dependent |
| Neighbor b | bitDepth bits | Direction-dependent |
| sao_type_idx | 2 bits | Selects direction (1-4) |

**Logic**:
```
sign_a = (c > a) ? 1 : (c < a) ? -1 : 0    // 2-bit signed
sign_b = (c > b) ? 1 : (c < b) ? -1 : 0    // 2-bit signed
edgeIdx = 2 + sign_a + sign_b               // 0-4
category = (edgeIdx == 2) ? 0 : edgeIdx     // Map flat to category 0
```

**Resources**: 2 comparators (bitDepth-bit) + 1 adder (3-bit) + mux. Combinational, 0 pipeline stages needed.

### BO Classifier

| Input | Width | Notes |
|-------|-------|-------|
| Sample value | bitDepth bits | Reconstructed sample |
| sao_band_position | 5 bits | Starting band |

**Logic**:
```
bandIdx = sample[bitDepth-1 : bitDepth-5]    // 5 MSBs (free: just wiring)
offset_idx = bandIdx - sao_band_position      // 5-bit subtract
active = (offset_idx <= 3) AND (offset_idx >= 0)  // Range check (unsigned: offset_idx < 4)
```

**Resources**: 1 subtractor (5-bit) + 1 comparator. Combinational.

### SAO Processing Order

SAO is applied after deblocking for the entire CTB. Processing order:

1. Read deblocked reconstructed samples for CTB
2. For each sample, classify (EO or BO)
3. Look up offset from 4-entry table
4. Add offset and clip
5. Write back to reconstructed picture buffer

**Throughput**: N samples/cycle (N = 4, 8, or 16 typical). For 64x64 CTB: 64*64 = 4096 samples per component.

### Line Buffer for EO

Vertical and diagonal EO classes need the above row's samples:

| EO Class | Extra Rows Needed | Line Buffer Size (4K luma) |
|----------|-------------------|---------------------------|
| EO_0 (horizontal) | 0 | 0 |
| EO_1 (vertical) | 1 | 3840 bytes (8-bit) |
| EO_2 (135-degree) | 1 | 3840 bytes |
| EO_3 (45-degree) | 1 | 3840 bytes |

**Shared with deblocking**: SAO line buffer can often be merged with deblocking's above-row buffer if processing is pipelined CTB-by-CTB.

### Parameter Storage (Frame Level)

| Resolution | CTBs (64x64) | SAO Params per CTB | Total |
|-----------|-------------|-------------------|-------|
| 1080p (1920x1080) | 30 x 17 = 510 | 9 bytes (3 components) | 4,590 bytes |
| 4K (3840x2160) | 60 x 34 = 2,040 | 9 bytes | 18,360 bytes |

Stored as a 2-D array indexed by CTB address. Updated during slice parsing.
