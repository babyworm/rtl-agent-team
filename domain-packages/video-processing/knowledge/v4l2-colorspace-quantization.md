# V4L2 Colorspace, Transfer Function, Quantization

## Metadata Fields to Treat as a Set

In V4L2, interpretation of pixel values is not fully described by FOURCC alone.
The following metadata must be handled consistently:

- `colorspace`
- `xfer_func`
- `ycbcr_enc`
- `quantization`

If these are mismatched, image may appear with wrong contrast, hue, or black/white levels
despite correct storage layout.

## Typical Operating Combinations

### SDR HD Video Pipeline

- `colorspace`: BT.709
- `ycbcr_enc`: BT.709
- `xfer_func`: BT.709 (or sRGB-like depending on pipeline policy)
- `quantization`: limited range (studio range)

### UHD / HDR-Capable Pipeline

- `colorspace`: BT.2020
- `ycbcr_enc`: BT.2020
- `xfer_func`: PQ or HLG according to content
- `quantization`: typically limited range for broadcast pipelines

## Quantization Handling

### Limited vs Full Range (8-bit example)

- Limited Y nominal range: 16..235
- Limited C nominal range: 16..240
- Full range: 0..255 for all components

Conversion implementations must explicitly map ranges during RGB<->YCbCr conversion.

## Practical Rules

1. Lock colorspace metadata before validating conversion matrices.
2. Validate matrix + quantization together using color bars and near-black/near-white patches.
3. Keep metadata attached to buffers through pipeline stages; do not drop on intermediate nodes.
4. For mixed SDR/HDR systems, explicitly define where OETF/EOTF conversion is performed.

## Validation Procedure

- Use one synthetic frame containing:
  - pure primaries (R/G/B/C/M/Y)
  - gray ramp
  - near-black and near-white patches
- Convert round-trip and check:
  - clipping behavior
  - level shifts due to range mismatch
  - channel cross-talk due to wrong matrix

## Reference Links

- v4.10 image format overview (metadata context):
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt.html
- V4L2 colorspace API page (current docs):
  https://docs.kernel.org/userspace-api/media/v4l/colorspaces-defs.html
