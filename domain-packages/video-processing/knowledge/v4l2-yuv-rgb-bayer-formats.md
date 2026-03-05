# V4L2 Format Families: YUV, RGB, Bayer

## Purpose

Quick reference for selecting source/destination storage formats before designing conversion
or DMA datapaths.

## YUV Formats (Frequently Used)

### `YUYV` (packed 4:2:2)

- Byte pattern repeats in 4-byte groups: Y0 Cb0 Y1 Cr0
- One plane, packed/interleaved
- Good for simple sensor/display interfaces, less cache-friendly for chroma-only operations

Reference:

- https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-yuyv.html

### `YU12` / `YV12` (planar 4:2:0)

- Three planes (Y, U, V) with 2x2 chroma subsampling
- `YU12` and `YV12` differ in U/V plane ordering

Reference:

- https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-yuv420.html

### `NV12` / `NV21` (semi-planar 4:2:0)

- Plane 0: Y
- Plane 1: interleaved chroma
- `NV12` uses UV order; `NV21` uses VU order

Reference:

- https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-nv12.html

### `NV12M` / `NV21M` / `NV12MT_16X16`

- Multi-planar variants or tiled variants
- Typically used when hardware allocates independent per-plane buffers or tile layout

Reference:

- https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-nv12m.html

## RGB Formats

V4L2 packed RGB formats differ by channel order and bit allocation (e.g., RGB565, XRGB8888,
ARGB8888 variants). Use exact FOURCC; do not infer channel order from memory dump names alone.

Reference:

- https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-packed-rgb.html

## Bayer Formats

Bayer formats represent one color sample per pixel by CFA pattern (RGGB/BGGR/GRBG/GBRG).
Demosaic stage is mandatory before full RGB domain operations.

Selection notes:

- choose pattern matching sensor metadata
- verify bit depth and packing (8/10/12-bit raw formats)

## Selection Heuristics

- Need encoder/decoder interop and common ISP path: start with `NV12`
- Need strict planar processing for independent U/V pipelines: `YU12`/`YV12`
- Need minimal conversion from 4:2:2 packed camera output: `YUYV`
- Need hardware tile compression/locality: consider `NV12MT_16X16`

## Conversion Risk Matrix

- `YUYV -> NV12`: unpack + vertical chroma decimation + UV interleave
- `YU12 -> NV12`: U/V merge and interleave, plane order check
- `NV12 <-> NV21`: UV byte swap only (easy but commonly missed)
- `Bayer -> RGB`: demosaic quality/latency trade-off dominates

## Reference Links

- v4.10 YUV format index:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/yuv-formats.html
- v4.10 pixel format definitions (FOURCC per format):
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt.html
