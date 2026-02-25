# H.265/HEVC Specification Summary

> Reference: ITU-T H.265 (V9) / ISO/IEC 23008-2

## Key Differences from H.264

| Feature | H.264/AVC | H.265/HEVC |
|---------|-----------|------------|
| Block Structure | Fixed 16x16 MB | Flexible CTU (8-64) with quad-tree |
| Intra Modes | 9 (4x4) + 4 (16x16) | 35 modes (all sizes) |
| Transform | 4x4 only | 4x4, 8x8, 16x16, 32x32 |
| Entropy | CAVLC/CABAC | CABAC only |
| Loop Filter | Deblocking only | Deblocking + SAO |
| MV Precision | 1/4 pel | 1/4 pel (8-tap filter) |

## Coding Tree Unit (CTU) Structure (§7.3.8.5)

- CTU sizes: 16x16, 32x32, 64x64
- Quad-tree split down to 8x8 CU minimum
- Each CU: Prediction Unit (PU) + Transform Unit (TU)
- TU uses Residual Quad-Tree (RQT): max depth configurable

## Intra Prediction (§8.4.4)

- 35 modes: Planar(0), DC(1), Angular(2-34)
- Angular modes cover 180° in 33 directions
- Reference sample filtering (strong/weak) based on mode and block size
- Available for all square sizes: 4x4 to 32x32

## SAO Filter (§8.7.3)

- Sample Adaptive Offset: per-CTB classification
- Two types: Edge Offset (EO) and Band Offset (BO)
- EO: 4 edge classes based on gradient direction
- BO: 32 bands based on sample value, offset for 4 consecutive bands

## HM Reference Software Function Map

| H.265 Section | HM Class/Function | Description |
|---------------|-------------------|-------------|
| §8.4.4 | `TComPrediction::xPredIntraAng()` | Angular intra prediction |
| §8.4.4 | `TComPrediction::xPredIntraPlanar()` | Planar intra prediction |
| §8.6.2 | `TComTrQuant::xT()` | Forward transform |
| §8.6.2 | `TComTrQuant::xIT()` | Inverse transform |
| §9.3 | `TEncBinCABACCounter` | CABAC encoding |
| §8.7.2 | `TComLoopFilter::xEdgeFilterLuma()` | Deblocking filter |
| §8.7.3 | `TComSampleAdaptiveOffset::offsetBlock()` | SAO filter |
