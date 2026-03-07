# Block-Level Conformance Verification for Video Codec Decoding

## Principle

For decoder designs, every processing block MUST produce bit-exact output matching the
reference software (JM for H.264, HM for H.265) at block boundaries. This is non-negotiable:
CABAC decoding output cannot differ, inverse TQ output cannot differ, prediction output
cannot differ. The standard defines exact arithmetic — there is only one correct answer.

This requirement applies across ALL implementation layers:
- **P2 Reference Model (refc/)** must match JM/HM at each block boundary
- **P3 BFM (bfm/)** must match Reference Model at each block boundary
- **P4 RTL (rtl/)** must match Reference Model at each block boundary
- **P5 Verification** confirms end-to-end with conformance bitstreams

## Reference Software

| Standard | Software | Decoder Binary | Source |
|----------|----------|---------------|--------|
| H.264/AVC | JM 19.0 | `ldecod` | https://iphome.hhi.de/suehring/jm/ |
| H.265/HEVC | HM 16.25 | `TAppDecoder` | https://vcgit.hhi.fraunhofer.de/jvet/HM |

## Block Boundaries (Decoder Pipeline)

### H.264 Decoder Blocks

```
Bitstream → [Syntax Parse] → [CABAC/CAVLC] → [Inverse Scan] → [Inverse TQ] → [Prediction] → [Reconstruction] → [Deblocking] → Output
```

| Block | Input (from upstream) | Output (to downstream) | JM Reference |
|-------|----------------------|----------------------|--------------|
| Syntax Parse | NAL unit bytes | Slice header, MB type, mode | `ldecod/src/nal.c`, `read_one_macroblock()` |
| CABAC Decode | Bitstream bits | Syntax elements (bin string) | `ldecod/src/cabac.c`, `readSyntaxElement_CABAC()` |
| Inverse Scan | Scan-ordered coefficients | 2D coefficient block | `ldecod/src/transform.c` |
| Inverse TQ | Quantized coefficients, QP | Residual block (pixel domain) | `ldecod/src/transform.c`, `inverse4x4()` + `dequant_4x4()` |
| Intra Prediction | Mode, neighbors | Predicted block | `ldecod/src/intra4x4.c`, `ldecod/src/intra16x16.c` |
| Inter Prediction | MV, reference frames | Predicted block | `ldecod/src/mc_prediction.c` |
| Reconstruction | Residual + predicted | Reconstructed block | `ldecod/src/macroblock.c` |
| Deblocking | Reconstructed frame, BS | Filtered frame | `ldecod/src/deblock.c`, `DeblockFrame()` |

### H.265 Decoder Blocks

```
Bitstream → [Syntax Parse] → [CABAC] → [Inverse Scan] → [Inverse TQ] → [Prediction] → [Reconstruction] → [Deblocking] → [SAO] → Output
```

| Block | Input | Output | HM Reference |
|-------|-------|--------|--------------|
| Syntax Parse | NAL unit bytes | Slice header, CTU structure | `TLibDecoder/TDecCAVLC.cpp` |
| CABAC Decode | Bitstream bits | Syntax elements | `TLibDecoder/TDecBinCoderCABAC.cpp` |
| Inverse Scan | Scan-ordered coefficients | 2D coefficient block | `TLibCommon/TComTrQuant.cpp` |
| Inverse TQ | Quantized coefficients, QP | Residual block | `TLibCommon/TComTrQuant.cpp`, `invTransformNxN()` |
| Intra Prediction | Mode, neighbors | Predicted block | `TLibCommon/TComPrediction.cpp`, `xPredIntraAng()` |
| Inter Prediction | MV, reference frames | Predicted block | `TLibCommon/TComPrediction.cpp`, `motionCompensation()` |
| Reconstruction | Residual + predicted | Reconstructed CU | `TLibDecoder/TDecCu.cpp` |
| Deblocking | Reconstructed frame | Deblocked frame | `TLibCommon/TComLoopFilter.cpp` |
| SAO | Deblocked frame, SAO params | SAO-filtered frame | `TLibCommon/TComSampleAdaptiveOffset.cpp` |

## Intermediate Data Extraction

To compare at block boundaries, extract intermediate data from JM/HM:

### JM (H.264)
```bash
# Build JM with trace enabled
cd JM/ldecod && make TRACE=1
# Decode with trace output
./ldecod -d decoder.cfg -p InputFile=conformance.264 -p OutputFile=decoded.yuv
# Trace files: trace_dec.txt (syntax), trace_coeff.txt (coefficients)
```

### HM (H.265)
```bash
# Build HM with RExt__DECODER_DEBUG_BIT_STATISTICS
cmake -DCMAKE_BUILD_TYPE=Debug -DRExt__DECODER_DEBUG_BIT_STATISTICS=ON ..
# Decode with trace
./TAppDecoder -b conformance.265 -o decoded.yuv --TraceFile=trace.txt --TraceRule="*:*"
```

### Block-Level Comparison Format

Each block should dump intermediate data in a standard format:
```
# Format: BLOCK_TYPE ADDR/INDEX VALUE_HEX
CABAC_BIN  mb=0,ctx=14  bin=1
INV_TQ     mb=0,blk=0   coeff=[0x0012,0xFFF3,0x0000,...]
PRED_OUT   mb=0,mode=0  pixel=[128,130,129,...]
RECON      mb=0         pixel=[140,142,138,...]
DEBLOCK    mb=0,edge=V  pixel=[139,141,138,...]
```

## Conformance Bitstreams

Use official conformance streams for end-to-end and block-level verification:

### H.264 (JCTVC → JVT)
| Stream Set | Purpose | Source |
|-----------|---------|--------|
| JVTG040 | Baseline Profile | ITU-T conformance |
| BA1_Sony_D | Baseline, all I | ITU-T conformance |
| CABAC_A | Main Profile CABAC | ITU-T conformance |
| CAMA1_Sony_C | CABAC, all modes | ITU-T conformance |

### H.265 (JVET → JCTVC)
| Stream Set | Purpose | Source |
|-----------|---------|--------|
| DBLK_A_* | Deblocking filter | JCTVC conformance |
| IPCM_A_* | PCM mode | JCTVC conformance |
| SAO_A_* | SAO filter | JCTVC conformance |
| TILES_A_* | Tile processing | JCTVC conformance |

Select a minimum representative subset per design target:
- **Minimal (3 streams)**: 1 all-intra + 1 P-frames + 1 B-frames
- **Standard (8 streams)**: Cover each decoder block with at least 1 dedicated stream
- **Full**: All available conformance streams for target profile/level

## Cross-Phase Verification Chain

```
              Block-level bitexact
P2 ref model ←──────────────────→ JM/HM reference software
      ↕ block-level bitexact
P3 BFM       ←──────────────────→ P2 ref model
      ↕ block-level bitexact
P4 RTL       ←──────────────────→ P2 ref model (via DPI-C or file I/O)
      ↕ end-to-end bitexact
P5 verify    ←──────────────────→ conformance bitstreams (JCTVC/JVET)
```

Each layer must be verified against the layer above at every block boundary.
A mismatch at any block boundary is a **hard failure** — there is no tolerance.

## Integration with Plugin Pipeline

| Phase | Agent | Action |
|-------|-------|--------|
| P2 | ref-model-dev | Build C ref model with per-block I/O dump. Verify vs JM/HM at each block boundary using conformance streams. |
| P3 | bfm-dev | BFM per-block I/O logs must match ref model per-block outputs for same input. |
| P4 | rtl-coder + p4s-unit-test | Unit tests feed conformance-derived vectors. Each RTL module output compared to ref model block output. |
| P5 | perf-verifier + codec-conformance-eval | End-to-end: decode conformance bitstreams in RTL, compare final YUV bitexact with JM/HM golden output. |
