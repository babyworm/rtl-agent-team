# Conformance Test Examples — Intentionally Empty

No worked example is committed here, **by design**: real codec conformance
inputs are large binary assets (ITU-T/JVT conformance bitstreams are
typically tens of MB each, licensed for distribution through the standards
bodies) and do not belong in a plugin repository.

## What an example WOULD contain

A complete conformance run consumes and produces:

| Artifact | Shape |
|----------|-------|
| Conformance bitstream(s) | JVT suite for H.264 (e.g. `CABA1_SVA_B.264`), JCT-VC suite for H.265 (e.g. `AMP_A_Samsung_7.bin`) placed at `sim/conformance/vectors/` |
| Golden reference output + MD5 refs | JM 19.0 / HM 16.20 decode output (`.yuv`) with the suite's published MD5 checksums at `sim/conformance/ref/` |
| Stream metadata | One `golden-metadata.json` per stream (schema: `../templates/golden-metadata.json` — standard, profile, level, JM/HM version, width, height, frame count) |
| Results | `sim/conformance/results.json` with per-vector PASS/FAIL and `divergence_byte`/`expected_hex`/`actual_hex` on FAIL (schema: `../references/conformance-test-conventions.md`) |

## How to acquire vectors (documented flow)

Follow the skill's documented flow (`../SKILL.md`):

1. Prerequisites: `conformance_report.json` from `ref-model` present, and
   JM 19.0 (H.264) or HM 16.20 (H.265) installed and on `PATH`.
2. Vector selection is Execution step 1: the
   `vcodec-syntax-entropy-expert` agent selects the applicable ITU-T JVT /
   JCT-VC conformance vectors for the target standard and profile/level.
   The suites are distributed by ITU-T/ISO (e.g. ITU-T T.871-series test
   material sites); place the chosen streams at `sim/conformance/vectors/`.
3. Byte-exact comparison uses the committed `../scripts/conformance_compare.py`;
   it needs only two files, so it can be exercised without any codec asset:

   ```sh
   python3 ../scripts/conformance_compare.py rtl_output.bin ref_output.bin
   ```

The deterministic script surface is therefore fully testable without the
binary assets; only the end-to-end vector runs require the downloaded
suites plus the JM/HM reference decoders.
