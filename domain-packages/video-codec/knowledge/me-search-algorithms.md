# Motion Estimation Search Algorithms

> ENCODER-SIDE ONLY — These algorithms are not normative; decoders only process transmitted MVs.

## Search Algorithm Overview

| Algorithm | Search Points (typ.) | Quality | Complexity | Use Case |
|-----------|---------------------|---------|------------|----------|
| Full Search (FS) | (2*SR+1)^2 | Optimal | Very high | Reference, small SR |
| Diamond Search (DS) | 15-30 | Good | Low | Real-time encoding |
| Hexagonal Search (HEXBS) | 11-20 | Good | Low | Alternative to DS |
| TZ Search | 20-80 | Near-optimal | Medium | HM/x265 default |
| Logarithmic Search | ~20 | Moderate | Very low | Legacy encoders |

SR = Search Range (typical: 64-128 pixels for HD, 256 for UHD).

## Full Search (Exhaustive)

Evaluates every integer-pel position within the search window.

- **Search points**: `(2*SR+1)^2` — e.g., SR=64 gives 16,641 points
- **Guaranteed optimal** for the given cost function
- **Hardware friendly**: Regular access pattern enables systolic array implementation

### Hardware Architecture (Systolic Array)

| Parameter | Typical Value | Notes |
|-----------|--------------|-------|
| PE array size | 16x16 or 8x8 | One PE per sample position |
| Throughput | 1 search point/cycle | All PEs compute SAD in parallel |
| Search range | Limited by array bandwidth | 64-pel common for hardware |
| Memory bandwidth | N^2 * (2*SR+1) bytes/block | Dominates power consumption |

## Diamond Search (DS)

Two-phase pattern: Large Diamond Search Point (LDSP) followed by Small Diamond Search Point (SDSP).

**LDSP** (9 points):
```
        x
      x x x
    x x C x x
      x x x
        x
```

**SDSP** (5 points):
```
      x
    x C x
      x
```

**Algorithm**:
1. Evaluate LDSP centered at predictor MV
2. If minimum is at center, switch to SDSP
3. If minimum is at edge, re-center LDSP and repeat
4. SDSP: evaluate 4 remaining points, select final minimum

Typical convergence: 2-4 LDSP iterations + 1 SDSP = 15-30 evaluations.

## Hexagonal Search (HEXBS)

**Hexagon pattern** (7 points):
```
      x   x
    x   C   x
      x   x
```

Followed by diamond refinement. Slightly better directional coverage than DS at similar cost.

## TZ Search (HM/x265 Default)

Combines multiple strategies for near-optimal results:

### Phase 1: Initial Search
1. Start at MV predictor (median, zero, or collocated)
2. **First search**: Diamond or square pattern at increasing distances (1, 2, 4, 8, ... up to SR)
3. Record best match at each distance level

### Phase 2: Raster Search (conditional)
- Triggered when best match distance > `iRaster` threshold (default: 5)
- Coarse grid search with step size = 5 over full search range
- Catches global minima missed by local search

### Phase 3: Refinement
- Star search pattern around current best
- Iterative refinement until no improvement
- Final 1-pel diamond refinement

### TZ Search Parameters (HM defaults)

| Parameter | Default | Description |
|-----------|---------|-------------|
| iSearchRange | 64 | Maximum search range |
| iRaster | 5 | Raster search trigger distance |
| bEnableRasterSearch | true | Enable raster phase |
| bStarRefinement | true | Enable star refinement |
| iStarStep | 1 | Star pattern step size |

## Integer-to-Sub-Pixel Cascade

All search algorithms operate at integer-pel first, then refine to sub-pixel:

### Step 1: Integer Motion Estimation
- Search algorithms above produce integer-pel MV
- Cost: SAD or SATD (see below)

### Step 2: Half-Pel Refinement
- Generate 8 half-pel positions around best integer-pel (diamond or square)
- Requires interpolation filter (H.264: 6-tap, H.265: 8-tap)
- Evaluate SATD at each position
- Select best half-pel or keep integer-pel

### Step 3: Quarter-Pel Refinement
- Generate 8 quarter-pel positions around best half-pel
- H.264: bilinear from integer+half; H.265: 8-tap at quarter positions
- Evaluate SATD, select final MV

**Typical sub-pel search**: 8 (half) + 8 (quarter) = 16 additional evaluations.

## Cost Models

### SAD (Sum of Absolute Differences)

`SAD = sum(|cur[x][y] - ref[x+mvx][y+mvy]|)` over block

| Property | Value |
|----------|-------|
| Complexity | N^2 absolute differences + N^2-1 additions |
| Hardware | Tree adder, 1-2 cycle latency for 8x8 |
| Accuracy | Moderate (no frequency weighting) |
| Use | Integer-pel search, fast modes |

### SATD (Sum of Absolute Transformed Differences)

`SATD = sum(|Hadamard(cur - ref)|)` — Hadamard transform of residual, then sum of absolutes.

| Property | Value |
|----------|-------|
| Complexity | Hadamard transform (add/sub only) + absolute + sum |
| Hardware | Butterfly network, 3-4 cycle latency for 8x8 |
| Accuracy | Good (approximates frequency-domain RD cost) |
| Use | Sub-pel refinement, mode decision |

### SSE (Sum of Squared Errors)

`SSE = sum((cur[x][y] - ref[x+mvx][y+mvy])^2)`

| Property | Value |
|----------|-------|
| Complexity | N^2 multiplies + N^2-1 additions |
| Accumulator width | 2*bitDepth + 2*log2(N) bits (e.g., 24 bits for 8-bit 8x8) |
| Use | Final RD cost computation (D in J=D+lambda*R) |

### Rate-Distortion Cost

`J = D + lambda * R(MV)`

- `D`: distortion (SAD, SATD, or SSE)
- `lambda`: Lagrange multiplier derived from QP
- `R(MV)`: estimated bits for MV (typically using MV difference from predictor)

**Lambda approximation**: `lambda_SAD ~ sqrt(lambda_SSE)`, `lambda_SSE ~ 0.85 * 2^((QP-12)/3)`

## Multi-Reference Strategy

| Feature | H.264 | H.265 |
|---------|-------|-------|
| Max reference frames | 16 (P), 32 (B) | 15 (each list) |
| Reference index cost | Exp-Golomb coded | Truncated unary (CABAC) |
| Typical search refs | 2-4 for speed | 2-4 for speed |
| Early termination | Skip if ref0 cost < threshold | Merge/skip mode check first |

**Hardware**: Multiple reference frames require multi-port or time-multiplexed reference memory access. Typical: search 1-2 references in parallel, remaining sequentially.

## Hardware Implementation Summary

| Component | Area (gates, est.) | Throughput |
|-----------|--------------------|------------|
| SAD 16x16 PE array | 30-50K | 1 search point/cycle |
| SATD 8x8 (Hadamard) | 15-25K | 1 block/4 cycles |
| MV cost estimator | 5-10K | 1 MV/cycle |
| Search controller (TZ) | 10-15K | Pattern-dependent |
| Sub-pel interpolator | 20-40K | 1 position/2 cycles |
