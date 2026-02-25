# JM (H.264 Reference Software) Function Map

> JM version: 19.0 (latest stable)
> Source: https://iphome.hhi.de/suehring/jm/

## Intra Prediction

| RTL Block | JM Source File | Function | Input | Output |
|-----------|---------------|----------|-------|--------|
| Intra 4x4 Mode Decision | `lencod/src/intra4x4.c` | `Mode_Decision_for_Intra4x4Macroblock()` | Reconstructed neighbors | Best mode per 4x4 block |
| Intra 4x4 Prediction | `lencod/src/intra4x4.c` | `Intra4x4_pred()` | Mode, neighbors | Predicted 4x4 block |
| Intra 16x16 Prediction | `lencod/src/intra16x16.c` | `Intra16x16_pred()` | Mode, neighbors | Predicted 16x16 block |
| Chroma Prediction | `lencod/src/intra_chroma.c` | `IntraChromaPrediction()` | Mode, neighbors | Predicted chroma block |

## Transform & Quantization

| RTL Block | JM Source File | Function | Notes |
|-----------|---------------|----------|-------|
| Forward 4x4 | `lencod/src/transform.c` | `forward4x4()` | Integer DCT approximation |
| Inverse 4x4 | `ldecod/src/transform.c` | `inverse4x4()` | Exact inverse |
| Hadamard 4x4 | `lencod/src/transform.c` | `hadamard4x4()` | For DC coefficients |
| Quantization | `lencod/src/quant.c` | `quant_4x4()` | QP-dependent scaling |
| Dequantization | `ldecod/src/quant.c` | `dequant_4x4()` | Inverse scaling |

## Entropy Coding

| RTL Block | JM Source File | Function | Notes |
|-----------|---------------|----------|-------|
| CABAC Init | `lencod/src/cabac.c` | `arienco_start_encoding()` | Initialize arithmetic coder |
| CABAC Encode | `lencod/src/cabac.c` | `biari_encode_symbol()` | Regular mode encoding |
| CABAC Bypass | `lencod/src/cabac.c` | `biari_encode_symbol_eq_prob()` | Bypass mode |
| CABAC Finish | `lencod/src/cabac.c` | `arienco_done_encoding()` | Flush and terminate |
| CAVLC | `lencod/src/vlc.c` | `writeSyntaxElement_CAVLC()` | Variable-length coding |

## Deblocking Filter

| RTL Block | JM Source File | Function | Notes |
|-----------|---------------|----------|-------|
| BS Calculation | `ldecod/src/deblock.c` | `GetStrength()` | Boundary strength 0-4 |
| Edge Filter | `ldecod/src/deblock.c` | `EdgeLoop()` | Apply filter to edge |
| Frame Filter | `ldecod/src/deblock.c` | `DeblockFrame()` | Filter entire frame |

## Test Vector Generation

```bash
# Encode with JM to generate reference vectors
./lencod -d encoder.cfg -p InputFile=foreman_cif.yuv \
  -p FramesToBeEncoded=10 \
  -p SourceWidth=352 -p SourceHeight=288

# Decode with JM to generate golden output
./ldecod -d decoder.cfg -p InputFile=test.264 \
  -p OutputFile=decoded.yuv
```
