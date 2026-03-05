# V4L2 Storage Layout Guide

## Why This Matters

Many conversion bugs are storage bugs, not color-math bugs. The DMA model must match V4L2
layout semantics exactly.

## API Structures

### Single-planar (`v4l2_pix_format`)

Key fields:

- `width`, `height`
- `pixelformat`
- `bytesperline`
- `sizeimage`
- colorspace metadata (`colorspace`, `ycbcr_enc`, `quantization`, `xfer_func`)

Use this when format is represented as one image surface in API terms.

### Multi-planar (`v4l2_pix_format_mplane`)

Key fields:

- `width`, `height`, `pixelformat`
- `num_planes`
- per-plane `plane_fmt[i].bytesperline`
- per-plane `plane_fmt[i].sizeimage`

Use this when each plane needs independent buffer bookkeeping.

## Plane Models

### Packed

Example: `YUYV`.

- One plane
- Luma/chroma samples interleaved in byte stream
- Single `bytesperline`/`sizeimage`

### Semi-planar

Example: `NV12`/`NV21` (single-plane or multi-plane variants).

- Luma plane + interleaved chroma plane
- Chroma plane half vertical resolution for 4:2:0
- UV order (`NV12`) vs VU order (`NV21`) is conversion-critical

### Planar

Example: `YU12`/`YV12`.

- Separate Y, Cb, Cr planes
- Chroma planes subsampled for 4:2:0
- U/V plane order differs by format

## Stride and Size Rules (Implementation Checklist)

1. `bytesperline` is typically aligned by hardware constraints, not only visible width.
2. `sizeimage` must include padding implied by stride and vertical alignment.
3. For multi-planar, compute both per-plane stride and per-plane size independently.
4. Never derive chroma plane stride by guess; derive from format + subsampling + alignment policy.

### Generic formulas (4:2:0 example)

Given:

- `Y_stride` = aligned luma bytes per line
- `H` = luma height

Then for common 4:2:0 layouts:

- Luma size: `Y_size = Y_stride * H`
- Chroma height: `Hc = H / 2`

If UV is interleaved (`NV12`/`NV21`):

- `UV_stride` often equals `Y_stride`
- `UV_size = UV_stride * Hc`
- Total: `sizeimage = Y_size + UV_size`

If U and V are separate (`YU12`/`YV12`):

- `U_stride` and `V_stride` often `Y_stride / 2` (subject to alignment)
- `U_size = U_stride * Hc`
- `V_size = V_stride * Hc`
- Total: `sizeimage = Y_size + U_size + V_size`

## Tiled / Vendor-Specific Layouts

Formats such as `NV12MT_16X16` use tiled memory rather than linear raster layout.

Implications:

- stride/size computations are tile-granular
- linear assumptions break
- conversion engine must support tile addressing or pre-linearization stage

## Validation Checklist

- [ ] Confirm API flavor (`pix` vs `pix_mp`)
- [ ] Confirm plane count and plane order
- [ ] Confirm UV/VU ordering
- [ ] Confirm stride alignment policy per plane
- [ ] Confirm `sizeimage` includes all padding
- [ ] Validate with deterministic memory dump inspection

## Reference Links

- v4.10 `v4l2_pix_format`:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-002.html
- v4.8 `v4l2_pix_format_mplane`:
  https://www.kernel.org/doc/html/v4.8/media/uapi/v4l/pixfmt-003.html
- current docs multi-planar page:
  https://docs.kernel.org/userspace-api/media/v4l/pixfmt-v4l2-mplane.html
- v4.10 `NV12M/NV21M/NV12MT_16X16`:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-nv12m.html
