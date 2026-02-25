# Published Video Codec VLSI Implementation Survey

## H.264 Encoder Implementations

| Reference | Target | Technology | Frequency | Gate Count | Power | Throughput |
|-----------|--------|-----------|-----------|-----------|-------|-----------|
| Chen (JSSC'06) | 1080p@30 Baseline | 180nm | 108 MHz | 289K gates | 186 mW | 1080p@30 |
| Huang (TCSVT'09) | 1080p@30 High | 90nm | 200 MHz | 510K gates | 120 mW | 1080p@30 |
| Liu (JSSC'12) | 4K@30 High | 40nm | 400 MHz | 1.2M gates | 280 mW | 4K@30 |
| Samsung (ISSCC'14) | 4K@60 High | 28nm | 500 MHz | ~2M gates | 150 mW | 4K@60 |

### Common H.264 Encoder Architecture Patterns

| Block | Typical Architecture | Area Share |
|-------|---------------------|-----------|
| Intra Prediction | 4-way parallel 4x4 + 16x16 mode eval | 15-20% |
| Inter Prediction (ME) | Hierarchical 3-level: IME → FME → sub-pel | 30-40% |
| Transform + Quant | Folded butterfly (shared forward/inverse) | 8-12% |
| CABAC | Dual-bin pipeline or multi-symbol | 10-15% |
| Deblocking | 2-pixel/cycle with 4-line transpose buffer | 8-10% |
| Recon + DPB | Line-buffer + SRAM-based frame store | 15-20% |

## H.265 Encoder Implementations

| Reference | Target | Technology | Frequency | Gate Count | Power | Throughput |
|-----------|--------|-----------|-----------|-----------|-------|-----------|
| Tikekar (JSSC'16) | 4K@30 Main | 40nm | 333 MHz | 4.8M gates | 510 mW | 4K@30 |
| Kim (JSSC'18) | 4K@60 Main 10 | 16nm | 500 MHz | ~6M gates | 200 mW | 4K@60 |
| MediaTek (ISSCC'19) | 8K@60 Main 10 | 7nm | 800 MHz | ~12M gates | 350 mW | 8K@60 |

### Common H.265 Encoder Architecture Patterns

| Block | Typical Architecture | Area Share |
|-------|---------------------|-----------|
| Intra Prediction | 35-mode parallel evaluator with CTU pipeline | 12-15% |
| Inter Prediction (ME) | TZ-search + SATD-based FME + merge mode eval | 25-35% |
| Transform | Multi-size (4/8/16/32) shared butterfly | 8-12% |
| Quantization | Rate-distortion optimized quant (RDOQ) | 5-8% |
| CABAC | Multi-bin bypass + regular pipeline | 8-12% |
| SAO | Pixel-parallel edge/band offset with line buffer | 5-8% |
| Deblocking | 4-sample parallel, strong/weak decision logic | 6-8% |
| CTU Controller | CU/PU/TU split decision (RDO-based) | 10-15% |

## H.264 Decoder Implementations

| Reference | Target | Technology | Frequency | Gate Count | Power | Throughput |
|-----------|--------|-----------|-----------|-----------|-------|-----------|
| Lin (JSSC'05) | 1080p@30 High | 180nm | 100 MHz | 95K gates | 42 mW | 1080p@30 |
| Kang (TCSVT'09) | 4K@30 High | 65nm | 200 MHz | 180K gates | 35 mW | 4K@30 |

## H.265 Decoder Implementations

| Reference | Target | Technology | Frequency | Gate Count | Power | Throughput |
|-----------|--------|-----------|-----------|-----------|-------|-----------|
| Bross (JSSC'16) | 4K@60 Main 10 | 28nm | 300 MHz | 450K gates | 65 mW | 4K@60 |
| Abeydeera (JSSC'18) | 8K@30 Main 10 | 16nm | 400 MHz | 800K gates | 55 mW | 8K@30 |

## SRAM Organization Patterns

### Line Buffer Sizing

| Block | Buffer Type | Size (1080p) | Size (4K) |
|-------|-----------|-------------|----------|
| Intra Prediction | Top-row reference | 1920 x 1 x 10b = 2.4 KB | 3840 x 1 x 10b = 4.8 KB |
| Deblocking | 4-line buffer | 1920 x 4 x 10b = 9.6 KB | 3840 x 4 x 10b = 19.2 KB |
| SAO | 1-line buffer + stats | 1920 x 1 x 10b + stats = 5 KB | 3840 x 1 x 10b + stats = 10 KB |
| Motion Estimation (local) | Search window | 64x64 x 8b = 4 KB | 128x128 x 8b = 16 KB |

### Reference Frame SRAM vs DRAM

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| On-chip SRAM (full) | Zero DRAM BW, deterministic | Very large (12+ MB for 1080p) | Low-res, ultra-low-power |
| On-chip SRAM (cache) | Reduced DRAM BW by 60-80% | Requires cache controller | 1080p-4K ASIC |
| External DRAM only | Minimal on-chip area | High BW requirement, latency | Cost-optimized designs |
| Tiled SRAM + DRAM | Balance of area vs BW | Complex management | High-end 4K/8K |

## Technology Scaling Trends

| Node | Gate Density (Mgates/mm2) | Typical Vdd | Typical Freq |
|------|--------------------------|------------|-------------|
| 180nm | 0.15 | 1.8V | 100-200 MHz |
| 90nm | 0.6 | 1.2V | 200-400 MHz |
| 40nm | 2.5 | 1.1V | 300-500 MHz |
| 28nm | 4.0 | 0.9V | 400-600 MHz |
| 16nm | 8.0 | 0.8V | 500-800 MHz |
| 7nm | 18.0 | 0.75V | 600-1000 MHz |
