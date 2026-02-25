# Video Codec Throughput Reference Tables

## H.264 Macroblock Rate (MB/s)

Macroblock size: 16x16 luma pixels. Values use ceiling division for partial blocks.

| Resolution | Frame Rate | MB/frame | MB/s |
|-----------|-----------|---------|------|
| 720p (1280x720) | 30 fps | 3,600 | 108,000 |
| 720p (1280x720) | 60 fps | 3,600 | 216,000 |
| 1080p (1920x1080) | 30 fps | 8,160 | 244,800 |
| 1080p (1920x1080) | 60 fps | 8,160 | 489,600 |
| 4K (3840x2160) | 30 fps | 32,400 | 972,000 |
| 4K (3840x2160) | 60 fps | 32,400 | 1,944,000 |
| 8K (7680x4320) | 30 fps | 129,600 | 3,888,000 |
| 8K (7680x4320) | 60 fps | 129,600 | 7,776,000 |

**Derivation**: `ceil(W/16) x ceil(H/16) x FPS`

### Cycles-per-MB Budget

| Target | Clock Freq | MB/s | Cycles/MB |
|--------|-----------|------|-----------|
| 1080p@30 | 200 MHz | 244,800 | 816 |
| 1080p@60 | 300 MHz | 489,600 | 612 |
| 4K@30 | 500 MHz | 972,000 | 514 |
| 4K@60 | 500 MHz | 1,944,000 | 257 |
| 4K@60 (85% util) | 500 MHz | 1,944,000 | 218 |

## H.265 CTU Rate (CTU/s)

CTU size: 64x64 luma pixels (maximum, Main Profile). Values use ceiling division.

| Resolution | Frame Rate | CTU/frame | CTU/s |
|-----------|-----------|----------|-------|
| 1080p (1920x1080) | 30 fps | 510 | 15,300 |
| 1080p (1920x1080) | 60 fps | 510 | 30,600 |
| 4K (3840x2160) | 30 fps | 2,040 | 61,200 |
| 4K (3840x2160) | 60 fps | 2,040 | 122,400 |
| 8K (7680x4320) | 30 fps | 8,160 | 244,800 |
| 8K (7680x4320) | 60 fps | 8,160 | 489,600 |

**Derivation**: `ceil(W/64) x ceil(H/64) x FPS`

### Cycles-per-CTU Budget

| Target | Clock Freq | CTU/s | Cycles/CTU |
|--------|-----------|-------|-----------|
| 1080p@30 | 200 MHz | 15,300 | 13,071 |
| 1080p@60 | 300 MHz | 30,600 | 9,803 |
| 4K@30 | 500 MHz | 61,200 | 8,169 |
| 4K@60 | 500 MHz | 122,400 | 4,084 |
| 8K@30 | 800 MHz | 244,800 | 3,267 |

## Memory Bandwidth Estimation

### H.264 Reference Frame Buffer

| Resolution | Bit Depth | Frames (DPB=4) | Size |
|-----------|----------|----------------|------|
| 1080p | 8-bit | 4 | 1920x1080x1.5x4 = 12.4 MB |
| 4K | 8-bit | 4 | 3840x2160x1.5x4 = 49.8 MB |
| 4K | 10-bit | 4 | 3840x2160x1.5x4x1.25 = 62.2 MB |

### H.265 Reference Frame Buffer

| Resolution | Bit Depth | Frames (DPB=6) | Size |
|-----------|----------|----------------|------|
| 1080p | 8-bit | 6 | 1920x1080x1.5x6 = 18.7 MB |
| 4K | 10-bit | 6 | 3840x2160x1.5x6x1.25 = 93.3 MB |
| 8K | 10-bit | 6 | 7680x4320x1.5x6x1.25 = 373.2 MB |

**Memory BW formula**: `Frame_size x FPS x (read_refs + write_recon) x overhead_factor`
- Typical read references per MB: 2-4 (P-frame), 4-8 (B-frame)
- Overhead factor: 1.3-1.5 (for sub-pixel interpolation, deblocking)
