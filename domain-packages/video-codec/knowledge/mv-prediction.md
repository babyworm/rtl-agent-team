# Motion Vector Prediction — H.264 & H.265

> References: H.264 §8.4.1; H.265 §8.5.3.1 (Merge), §8.5.3.2 (AMVP)

## H.264 Median MV Prediction (§8.4.1)

### Spatial Neighbors

```
  B2  B   B1
  A  [cur]
```

| Neighbor | Position | Description |
|----------|----------|-------------|
| A | Left | Left-most partition on the same row |
| B | Above | Above partition directly above |
| B1 | Above-right | Above-right of current partition |
| B2 | Above-left | Above-left (fallback when B1 unavailable) |

**Priority**: Use B1 (above-right); if unavailable, use B2 (above-left).

### Prediction Rules (§8.4.1.3)

| Condition | Predicted MV |
|-----------|-------------|
| All three available | `median(mvA, mvB, mvC)` where C = B1 or B2 |
| Only one available | Copy that MV |
| Two available (one = B2 fallback) | `median(mvA, mvB, mvB2)` |
| 16x8 top partition | mvB (above) |
| 16x8 bottom partition | mvA (left) |
| 8x16 left partition | mvA (left) |
| 8x16 right partition | mvC (above-right or above-left) |

**Median computation**: `median(a,b,c) = a + b + c - min(a,b,c) - max(a,b,c)` per component (x,y separately).

### Direct Mode (B-slices, §8.4.1.2)

- **Temporal direct**: MV derived from co-located MB in reference list 1
  - `mv_L0 = (td != 0) ? Clip3(-32768, 32767, (tb * mv_col * 256 + 128) / (256 * td)) : mv_col`
  - `td = DiffPicOrderCnt(ref_L1[0], ref_col)`, `tb = DiffPicOrderCnt(cur, ref_L0[mapped])`
- **Spatial direct**: Derived from spatial neighbors A, B, C using median

## H.265 Merge Mode (§8.5.3.1)

### Merge Candidate List (up to 5 candidates)

Derived in strict order; duplicates pruned at each step.

#### Step 1: Spatial Candidates (§8.5.3.2.2)

Check order: **A1 → B1 → B0 → A0 → B2**

```
  B2  B1  B0
  A0 [cur PU]
  A1
```

| Candidate | Position | Condition to include |
|-----------|----------|---------------------|
| A1 | Below-left | Available AND not inter-predicted with same ref+MV as current |
| B1 | Above-right | Available AND not identical to A1 |
| B0 | Above | Available AND not identical to B1 |
| A0 | Left | Available AND not identical to A1 |
| B2 | Above-left | Only if < 4 candidates so far; not identical to A0 or B1 |

**Pruning rule**: Each new candidate is compared against previously added candidates. If MV and reference index match an existing entry, the candidate is skipped.

#### Step 2: Temporal Candidate (§8.5.3.2.8)

- Co-located PU from reference picture in list 0 or list 1
- Position: bottom-right of co-located PU; if unavailable, center
- MV scaling: `mv_scaled = Clip3(-32768, 32767, Sign(distScaleFactor * mv_col) * ((Abs(distScaleFactor * mv_col) + 127) >> 8))`
- `distScaleFactor = Clip3(-4096, 4095, (tb * (16384 + Abs(td)/2) / td))`
- Only added if total candidates < 5

#### Step 3: Combined Bi-Predictive Candidates (§8.5.3.2.9)

If still < 5 candidates AND B-slice: combine L0 MV from one candidate with L1 MV from another.

Combination pairs (in order): (0,1), (1,0), (0,2), (2,0), (1,2), (2,1), (0,3), (3,0).

#### Step 4: Zero MV Candidates

Fill remaining slots with zero-MV entries using available reference indices (0, 1, 2, ...).

### Merge Index Signaling

- Truncated unary binarization, max = `MaxNumMergeCand - 1` (typically 4)
- First bin CABAC-coded, remaining bins bypass-coded
- Typical: merge_idx=0 costs 1 bin (most frequent)

## H.265 AMVP (Advanced MV Prediction, §8.5.3.2)

### AMVP Candidate List (exactly 2 candidates)

#### Step 1: Left Candidates (§8.5.3.2.6)

Check **A0** then **A1**. Select the first that:
- Is available
- Uses the same reference picture as the current PU (same POC)

If neither matches with same reference, retry with **scaled MV** (any reference, scaled by POC distance).

#### Step 2: Above Candidates (§8.5.3.2.6)

Check **B0** then **B1** then **B2**. Same matching logic as left:
- First with same reference picture
- If none, first with any reference (scaled)

**Pruning**: If above candidate equals left candidate, skip it.

#### Step 3: Temporal Candidate (§8.5.3.2.8)

- Same derivation as merge temporal candidate
- Only if < 2 candidates after spatial

#### Step 4: Zero MV

Fill to 2 candidates with zero MV if needed.

### MV Difference Coding

After selecting AMVP predictor (index 0 or 1):
- `mvd = mv - mvp[amvp_idx]`
- mvd coded with Exp-Golomb in CABAC (sign + abs_mvd_greater0 + abs_mvd_greater1 + abs_mvd_minus2)

## MV Scaling

Used for temporal candidates and cross-reference-picture prediction:

```
td = DiffPicOrderCnt(colPic, colRefPic)
tb = DiffPicOrderCnt(curPic, curRefPic)
tx = (16384 + Abs(td)/2) / td
distScaleFactor = Clip3(-4096, 4095, (tb * tx + 32) >> 6)
mv_scaled = Clip3(-32768, 32767, Sign(x) * ((Abs(x) + 127) >> 8))
  where x = distScaleFactor * mv_col
```

**Precision**: Scale factor is Q6 (6 fractional bits). MV values are in quarter-pel units (14-bit signed).

## Hardware Implementation Notes

### Merge Candidate Derivation

| Stage | Operation | Latency (cycles) |
|-------|-----------|-------------------|
| Spatial fetch | Read A1,B1,B0,A0,B2 from neighbor storage | 1-2 |
| Pruning | Compare each new candidate against existing list | 1 per candidate |
| Temporal | Fetch co-located MV + scaling | 2-3 (memory latency) |
| Combined bi-pred | Combine L0/L1 pairs | 1 |
| Zero fill | Append zero MVs | 1 |
| **Total** | | **5-8 cycles** |

### Storage Requirements

| Data | Width | Per CU | Notes |
|------|-------|--------|-------|
| MV (x,y) | 2 * 16 bits = 32 bits | Per 4x4 sub-block | Quarter-pel, signed |
| Reference index | 4 bits (L0) + 4 bits (L1) | Per 4x4 sub-block | Max 15 refs per list |
| Prediction mode | 2 bits | Per PU | Intra/Inter L0/L1/Bi |
| Merge flag | 1 bit | Per PU | Merge vs AMVP |
| Merge index | 3 bits | Per PU | 0-4 |

**Neighbor storage**: Above row (1 CTU row of MVs) + left column (1 CTU height).
For 64x64 CTU at 4x4 granularity: above = 16 entries/CTU * picture_width_in_CTU, left = 16 entries.

### Critical Path

- **Merge**: Spatial candidate pruning is sequential (A1 checked first, then B1 vs A1, then B0 vs B1 and A1, etc.). 5-candidate pruning requires 1+1+2+2+2 = 8 comparisons, but can be pipelined.
- **AMVP**: Simpler (2 candidates, 1 pruning check), typically 3-4 cycles.
- **Temporal scaling**: Multiply + shift, 1-2 cycles depending on multiplier implementation.
