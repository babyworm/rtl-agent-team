# FOURCC Cheat Sheet (Storage-Centric)

## Quick Comparison

| FOURCC | Chroma | Layout | Plane Count | Typical Use | Common Pitfall |
|---|---|---|---:|---|---|
| `YUYV` | 4:2:2 | packed | 1 | camera capture, legacy interfaces | mistaken byte parsing |
| `YU12` | 4:2:0 | planar | 3 | software pipelines needing separate U/V | confused with `YV12` |
| `YV12` | 4:2:0 | planar | 3 | same as above with swapped chroma planes | U/V order inversion |
| `NV12` | 4:2:0 | semi-planar (UV) | 2 (logical) | codec/ISP interop, common HW path | treated as `NV21` |
| `NV21` | 4:2:0 | semi-planar (VU) | 2 (logical) | mobile camera/display paths | UV swap bug |
| `NV12M` | 4:2:0 | multi-planar (UV) | 2 | independent plane buffers | contiguous assumption |
| `NV21M` | 4:2:0 | multi-planar (VU) | 2 | independent plane buffers | UV/VU swap + API mismatch |
| `NV12MT_16X16` | 4:2:0 | tiled | vendor/tile-specific | bandwidth/locality optimization | linear addressing assumption |

## API Mapping Reminder

- Single-planar API: `v4l2_pix_format`
- Multi-planar API: `v4l2_pix_format_mplane`

Do not infer API from format name alone; validate driver capabilities and negotiated format.

## Selection Tips

- Prefer `NV12` when targeting broad codec and hardware compatibility.
- Use multi-planar variants when planes are separately allocated by hardware.
- Use tiled variants only if full tile-aware pipeline support is present.

## Minimal Bring-Up Checklist

- [ ] Confirm negotiated FOURCC from `VIDIOC_G_FMT`.
- [ ] Confirm API struct in use (`pix` or `pix_mp`).
- [ ] Confirm per-plane stride and size.
- [ ] Validate with known test pattern.
- [ ] Verify color metadata fields are propagated.

## Reference Links

- v4.10 image format index:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt.html
- v4.10 pixel format definitions (FOURCC per format):
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt.html
- v4.10 NV12M/NV21M/NV12MT_16X16:
  https://www.kernel.org/doc/html/v4.10/media/uapi/v4l/pixfmt-nv12m.html
