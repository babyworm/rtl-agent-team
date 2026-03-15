# RDOQ — Rate-Distortion Optimized Quantization

> ENCODER-SIDE ONLY — RDOQ is not normative; decoders receive standard quantized levels.
> References: HM encoder (TEncSbac::xRateCoeffLevel), x265 (rdoQuant)

## Overview

Standard quantization rounds each coefficient independently using a fixed dead-zone offset. RDOQ considers the **rate cost** (bits) of each quantization decision, choosing levels that minimize the RD cost `J = D + lambda * R`.

| Aspect | Standard Quantization | RDOQ |
|--------|----------------------|------|
| Decision | Per-coefficient, independent | Per-coefficient + group-level |
| Cost model | Distortion only | Distortion + rate |
| Dead-zone | Fixed (1/3 intra, 1/6 inter) | Adaptive (varies by coefficient) |
| Complexity | 1 multiply + shift per coeff | Multiple RD evaluations per coeff |
| Coding gain | Baseline | 2-5% BD-rate improvement |

## RD Cost Model

### Cost Function

```
J = D + lambda * R
```

| Term | Definition | Units |
|------|-----------|-------|
| D | `(coeff - level * Qstep)^2` | Squared error (distortion) |
| R | Estimated bits for `level` (CABAC model) | Bits |
| lambda | `0.85 * 2^((QP-12)/3)` (SSE-based) | Distortion/bit trade-off |

### Lambda Derivation

| QP | lambda_SSE | lambda_SAD (approx.) |
|----|-----------|---------------------|
| 12 | 0.85 | 0.92 |
| 18 | 3.40 | 1.84 |
| 24 | 13.6 | 3.69 |
| 30 | 54.4 | 7.37 |
| 36 | 217.6 | 14.75 |
| 42 | 870.4 | 29.50 |

Lambda scales with QP: higher QP means rate matters more relative to distortion.

## RDOQ Decision Levels

### Per-Coefficient Decision

For each coefficient with standard quantized level `L`, evaluate:

| Candidate | Level | Distortion | Rate | Total J |
|-----------|-------|------------|------|---------|
| Keep L | L | D(L) | R(L) | D(L) + lambda*R(L) |
| Floor L-1 | L-1 | D(L-1) | R(L-1) | D(L-1) + lambda*R(L-1) |
| Zero | 0 | D(0) | R(0) | D(0) + lambda*R(0) |

Select the candidate with minimum J.

**Key insight**: Zeroing a coefficient may increase distortion but saves significant rate (especially if it eliminates a non-zero significance flag or changes the last-significant position).

### Rate Estimation Components

For a single coefficient level, the rate includes:

| Syntax Element | Condition | Estimated Bits |
|----------------|-----------|---------------|
| sig_coeff_flag | Always | p_sig (from CABAC context) |
| coeff_abs_level_greater1_flag | level >= 1 | p_gt1 |
| coeff_abs_level_greater2_flag | level >= 2 | p_gt2 |
| coeff_abs_level_remaining | level >= 3 | Exp-Golomb-Rice bits |
| coeff_sign_flag | level != 0 | 1 bit (bypass) |

**CABAC rate estimation**: `rate = -log2(p_context)` bits. Implemented as table lookup indexed by CABAC state.

## Last Significant Position Optimization

### Problem

The `last_sig_coeff_x/y` syntax signals where the last non-zero coefficient is in scan order. Changing this position affects the rate of all subsequent coefficients.

### Algorithm

Scan coefficients in reverse order. For each potential last-significant position:

```
J_total(last_pos) = sum(J_coeff[i], i=0..last_pos) + R(last_sig_x, last_sig_y) * lambda
```

where `J_coeff[i]` is the per-coefficient RD cost assuming position i is within the coded region.

**Optimization**: Evaluate `J_total` at each non-zero position in reverse scan. Track the minimum. This determines both the optimal last position and per-coefficient levels.

### Scan Order Interaction

| Transform Size | Scan Type | Condition |
|---------------|-----------|-----------|
| 4x4 | Diagonal up-right | Default |
| 4x4 | Horizontal | Intra, nearly horizontal prediction |
| 4x4 | Vertical | Intra, nearly vertical prediction |
| 8x8+ | Diagonal up-right | Always (sub-block scan) |

H.265 uses **sub-block scanning**: 4x4 coefficient groups scanned in diagonal order, with `coded_sub_block_flag` per group.

## Floor vs Ceil Trade-Off

### Dead-Zone Analysis

Standard quantization uses a dead-zone around zero:

```
Standard: level = floor((|coeff| * MF + f) >> qbits)
```

where `f` controls the dead-zone width:
- `f = qstep/3` (intra): smaller dead-zone, fewer zeros, higher quality
- `f = qstep/6` (inter): larger dead-zone, more zeros, better compression

RDOQ effectively creates an **adaptive dead-zone** per coefficient:
- Coefficients where zeroing saves many bits: larger effective dead-zone
- Coefficients where the level is cheap to code: smaller effective dead-zone

### Soft Quantization Effect

RDOQ tends to:
1. **Zero out** isolated non-zero coefficients (high rate for significance)
2. **Preserve** coefficients near other non-zeros (shared sub-block flag cost)
3. **Reduce** the last-significant position when tail coefficients are small
4. **Round down** more aggressively at high QP (rate dominates)
5. **Round up** more at low QP when distortion dominates

## Implementation Complexity

### Computational Cost per TU

| Operation | Count (NxN TU) | Notes |
|-----------|---------------|-------|
| Level candidates | 2-3 per non-zero coeff | L, L-1, 0 |
| Distortion computation | 2-3 per non-zero | Multiply + subtract + square |
| Rate estimation | 2-3 per non-zero | CABAC table lookup |
| J comparison | 2-3 per non-zero | Add + compare |
| Last-pos evaluation | Up to N^2 positions | Cumulative sum update |

### Simplifications for Hardware

| Simplification | Impact on Compression | Complexity Reduction |
|---------------|----------------------|---------------------|
| Skip candidates with level > L | Negligible | Eliminates ceil evaluation |
| Rate table (pre-computed) | None (exact) | Replaces log2 with ROM lookup |
| Group-level decision only | 0.1-0.3% BD-rate loss | 4x fewer evaluations |
| Fixed lambda (no per-coeff) | Negligible | Eliminates lambda recomputation |
| Truncated candidate set | 0.05% BD-rate loss | Only evaluate L and 0 |

### Hardware Architecture

```
Input: quantized levels[N*N], transform coeffs[N*N]

For each scan position (reverse order):
  ┌──────────────┐
  │ Distortion    │─── D(L), D(L-1), D(0)
  │ Calculator    │
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │ Rate          │─── R(L), R(L-1), R(0) from CABAC state LUT
  │ Estimator     │
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │ J = D + λR   │─── Compare 3 candidates
  │ Comparator    │
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │ Last-Pos     │─── Cumulative J tracking
  │ Tracker       │
  └──────────────┘

Output: optimized levels[N*N], last_sig_pos
```

**Throughput**: 1-2 coefficients/cycle (limited by rate estimation table access).

### Rate Estimation Table

| Table | Entries | Width | Size |
|-------|---------|-------|------|
| CABAC state → rate (significance) | 64 states | 15 bits (Q15 fixed-point) | 128 bytes |
| CABAC state → rate (gt1) | 64 states | 15 bits | 128 bytes |
| CABAC state → rate (gt2) | 64 states | 15 bits | 128 bytes |
| Exp-Golomb-Rice rate | 32 entries | 8 bits | 32 bytes |
| **Total** | | | ~416 bytes |
