# CAVLC Coding Tables — H.264

> Reference: H.264 §9.2

## Overview

Context-Adaptive Variable-Length Coding (CAVLC) is used in H.264 Baseline/Main profiles for residual coefficient coding. Not used in H.265 (CABAC only).

**Coding order for a 4x4 block**:
1. `coeff_token` — number of non-zero coefficients (TotalCoeff) + trailing ones (T1s)
2. Sign of trailing ones (1 bit each, reverse scan order)
3. `level` values (remaining non-zero coefficients, reverse scan order)
4. `total_zeros` — number of zeros before last non-zero coefficient
5. `run_before` — run of zeros before each non-zero coefficient

## nC Derivation (§9.2.1)

The context number `nC` selects the VLC table for `coeff_token`:

```
nC = (nA + nB + 1) >> 1    (both available)
nC = nA                      (only left available)
nC = nB                      (only above available)
nC = 0                       (neither available)
```

where `nA` = TotalCoeff of left 4x4 block, `nB` = TotalCoeff of above 4x4 block.

| nC Range | VLC Table | Typical Content |
|----------|-----------|-----------------|
| 0, 1 | Table 9-5 (Num-VLC0) | Low activity (smooth areas) |
| 2, 3 | Table 9-6 (Num-VLC1) | Medium activity |
| 4, 5, 6, 7 | Table 9-7 (Num-VLC2) | High activity |
| 8+ | Table 9-8 (FLC) | Very high activity (6-bit fixed length) |

**Special cases**:
- Chroma DC (2x2): `nC = -1`, uses separate Table 9-5(chroma)
- Chroma DC (2x4, 4:2:2): `nC = -2`, uses separate table

## Coeff_token Tables (§9.2.1, Tables 9-5 through 9-8)

### Table 9-5 (nC = 0,1) — Excerpt

| TotalCoeff | TrailingOnes | Code | Length |
|------------|-------------|------|--------|
| 0 | 0 | 1 | 1 |
| 1 | 1 | 01 | 2 |
| 2 | 2 | 0011 | 4 |
| 1 | 0 | 000101 | 6 |
| 3 | 3 | 000011 | 6 |
| 4 | 3 | 0000011 | 7 |
| 5 | 3 | 00000011 | 8 |

**Pattern**: Higher TotalCoeff values use longer codes. TrailingOnes=3 (maximum) is common.

### Table 9-8 (nC >= 8) — Fixed Length

| TotalCoeff | TrailingOnes | Code | Length |
|------------|-------------|------|--------|
| All | All valid | `{TrailingOnes[1:0], TotalCoeff[3:0]}` | 6 |

All entries are 6 bits: 2 bits for T1 count + 4 bits for TotalCoeff.

## Level Coding (§9.2.2)

### Level Prefix

| levelSuffixSize | Threshold for level promotion |
|----------------|-------------------------------|
| 0 (initial, TotalCoeff > 10 and T1s < 3) | |
| 0 (initial, otherwise) | |
| Increment when: | `Abs(level) > (3 << (suffixLength-1))` |

**level_prefix**: Unary code (count leading zeros before a 1-bit).

**level_suffix**: `levelSuffixSize` bits following the prefix.

### Level VLC Encoding

```
levelCode = 2 * Abs(level) - 2 + sign    (sign: 0 for positive, 1 for negative)
level_prefix = levelCode >> suffixLength
level_suffix = levelCode - (level_prefix << suffixLength)
```

**Suffix length adaptation** (initialized based on TotalCoeff and TrailingOnes):

| Condition | Initial suffixLength |
|-----------|---------------------|
| TotalCoeff > 10 AND TrailingOnes < 3 | 1 |
| Otherwise | 0 |

After each level coded, if `Abs(level) > threshold[suffixLength]`:
- `suffixLength++`
- Thresholds: {0, 3, 6, 12, 24, 48, N/A}

## Total Zeros (§9.2.3)

### total_zeros VLC Tables (Tables 9-9, 9-10)

Separate VLC table for each `TotalCoeff` value (1..15 for 4x4, 1..3 for 2x2 chroma DC).

| TotalCoeff | Max total_zeros | Table Entries |
|------------|----------------|---------------|
| 1 | 15 | 16 entries |
| 2 | 14 | 15 entries |
| 3 | 13 | 14 entries |
| ... | ... | ... |
| 15 | 1 | 2 entries |

**Total**: 120 VLC codewords for 4x4 blocks.

## Run Before (§9.2.4)

### run_before VLC (Table 9-11)

Coded for each non-zero coefficient (except the last) in reverse scan order. Table selected by `zerosLeft`.

| zerosLeft | Max run_before | Code Examples |
|-----------|---------------|---------------|
| 1 | 1 | 0→1, 1→0 |
| 2 | 2 | 0→1, 1→01, 2→00 |
| 3 | 3 | 0→11, 1→10, 2→01, 3→00 |
| 4 | 4 | 0→11, 1→10, 2→01, 3→001, 4→000 |
| 5 | 5 | 0→11, 1→10, 2→011, 3→010, 4→001, 5→000 |
| 6 | 6 | 0→11, 1→000, 2→001, 3→010, 4→011, 5→10, 6→000... |
| 7+ | min(6, zerosLeft) | Same as zerosLeft=7 |

**Termination**: Last non-zero coefficient's run is inferred (no coding needed): `run_last = zerosLeft - sum(coded_runs)`.

## Scan Order

### 4x4 Block Zig-Zag (Frame Mode)

```
 0  1  5  6
 2  4  7 12
 3  8 11 13
 9 10 14 15
```

### 4x4 Block Field Scan

```
 0  2  8 12
 1  5  9 13
 3  6 10 14
 4  7 11 15
```

### 8x8 Block Scan (High Profile)

64-element zig-zag scan defined in Table 8-16.

## Hardware Implementation Notes

### VLC Decoder Architecture

| Component | Size | Notes |
|-----------|------|-------|
| coeff_token ROM | 4 tables x ~64 entries x 6 bits | ~192 bytes |
| total_zeros ROM | 15 tables x ~16 entries x 4 bits | ~120 bytes |
| run_before ROM | 7 tables x 7 entries x 3 bits | ~21 bytes |
| nC computation | 5-bit adder + shift | From neighbor TotalCoeff |
| Level decoder | FSM + suffix length tracker | Adaptive VLC |

### Decoding Pipeline

| Stage | Operation | Cycles |
|-------|-----------|--------|
| 1 | Compute nC from neighbors | 1 |
| 2 | Decode coeff_token (variable length) | 1-3 (bit-serial) |
| 3 | Decode trailing one signs | 0-3 (1 bit each) |
| 4 | Decode levels (variable per coefficient) | TotalCoeff - T1s cycles |
| 5 | Decode total_zeros | 1 |
| 6 | Decode run_before values | TotalCoeff - 1 cycles (worst case) |

**Total**: 3 + TotalCoeff + (TotalCoeff-1) cycles worst case for a 4x4 block.

### Throughput Consideration

CAVLC is inherently serial (variable-length codes require sequential bit parsing). Hardware decoders typically use:
- **Multi-symbol lookup**: Decode up to 16 bits in one cycle using ROM lookup
- **Barrel shifter**: Consume variable number of bits per cycle
- **Dual-table lookup**: Parallel decode of prefix and suffix for levels
