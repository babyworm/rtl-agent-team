# V4L2 Pixel Format Overview (Format Conversion + Storage)

## Scope

This guide summarizes how to reason about V4L2 pixel formats for hardware/software
integration work, with focus on:

- format conversion planning (RGB/YUV/Bayer)
- storage layout (single-planar vs multi-planar)
- buffer sizing (`bytesperline`, `sizeimage`)
- colorspace metadata (`colorspace`, `xfer_func`, `ycbcr_enc`, `quantization`)

Primary reference baseline:

- Linux kernel media userspace API v4.10, Image Formats index
- Supplemental references for multi-planar details from v4.8 and current docs

## Core Concepts

### 1. `pixelformat` is storage + sample interpretation

A V4L2 FOURCC encodes both sample organization and memory storage rules. Two formats with
same nominal color model can still require different DMA and conversion logic due to different
plane count, stride behavior, or chroma placement.

### 2. Single-planar vs multi-planar APIs

- **Single-planar**: `struct v4l2_pix_format` (`pix`)
- **Multi-planar**: `struct v4l2_pix_format_mplane` (`pix_mp`)

Multi-planar is required for formats represented as separate planes with independent stride
and size bookkeeping, and for many hardware blocks that expose independent DMA surfaces.

### 3. Conversion correctness has two dimensions

A conversion path is correct only when both are correct:

- **Math**: matrix/transfer function/quantization mapping
- **Storage**: plane order, byte order, chroma siting, stride, image size

## Practical Decision Flow

1. Identify source and destination FOURCC.
2. Determine plane model (single vs multi-planar API).
3. Confirm chroma model (4:2:0/4:2:2/4:4:4) and chroma order (UV vs VU).
4. Confirm colorspace metadata side fields:
   - `colorspace`
   - `xfer_func`
   - `ycbcr_enc`
   - `quantization`
5. Compute per-plane stride and size (`bytesperline`, `sizeimage`).
6. Validate with a deterministic test pattern (color bars + checkerboard + gradients).

## Common Failure Modes

- Treating `NV12` and `NV21` as interchangeable (UV/VU swapped)
- Assuming contiguous memory when using multi-planar variant (`NV12M`, `NV21M`)
- Ignoring chroma phase/siting when up/down sampling
- Using luma/chroma conversion matrix without matching `ycbcr_enc` and `quantization`
- Underestimating `sizeimage` by forgetting alignment padding

## Reference Links

- v4.10 image format index:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt.html
- v4.10 single-planar struct (`v4l2_pix_format`):
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-002.html
- v4.8 multi-planar struct (`v4l2_pix_format_mplane`) fallback:
  https://www.kernel.org/doc/html/v4.8/media/uapi/v4l/pixfmt-003.html
- current docs multi-planar page:
  https://docs.kernel.org/userspace-api/media/v4l/pixfmt-v4l2-mplane.html
