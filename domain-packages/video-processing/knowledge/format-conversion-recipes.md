# Format Conversion Recipes (V4L2-Oriented)

## Purpose

Provide implementation-oriented conversion checklists that include both color math and storage
layout handling.

## Recipe 1: `YUYV` -> `NV12`

### Steps

1. Parse packed stream as `(Y0, Cb, Y1, Cr)` groups.
2. Write luma samples to Y plane raster order.
3. For each 2x2 luma block, generate one chroma pair (UV) for `NV12`.
4. Store chroma interleaved in UV order.
5. Set metadata (`colorspace`, `ycbcr_enc`, `quantization`) to match source/capture policy.

### Storage Notes

- Input is packed 4:2:2 single-plane; output is semi-planar 4:2:0.
- Vertical chroma downsample is required.

## Recipe 2: `YU12` <-> `NV12`

### `YU12` -> `NV12`

- Keep Y plane as-is (stride permitting).
- Interleave U and V planes into UV bytes.

### `NV12` -> `YU12`

- Split UV interleaved plane into separate U and V planes.

### Risk

- U/V order mistakes when source was actually `YV12`.

## Recipe 3: `NV12` <-> `NV21`

- Same subsampling and plane sizes.
- Conversion is UV byte swap per chroma pair.

## Recipe 4: `RGB888` -> `NV12`

1. Apply RGB->YCbCr matrix (match BT.601/709/2020 policy).
2. Apply quantization mapping (limited/full as configured).
3. Subsample chroma to 4:2:0.
4. Write Y plane and UV interleaved plane.

### Fixed-Point Guidance

- Use Q-format coefficients with explicit rounding mode.
- Validate peak error against floating-point reference on ramp and saturated colors.

## Buffer Sizing Checklist

- [ ] Confirm width/height alignment requirements.
- [ ] Compute per-plane stride (`bytesperline`) with alignment.
- [ ] Compute per-plane `sizeimage` with padded height.
- [ ] For multi-planar API, fill each `plane_fmt[i]` independently.

## Conformance-Style Test Set

- SMPTE color bars
- gray ramp (0..255 or bit-depth equivalent)
- checkerboard chroma stress pattern
- odd width/height frame (alignment edge case)
- tiled input sample (if supporting tiled FOURCC)

## Reference Links

- v4.10 pixfmt index:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt.html
- v4.10 YUYV:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-yuyv.html
- v4.10 YUV420:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-yuv420.html
- v4.10 NV12/NV21:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-nv12.html
