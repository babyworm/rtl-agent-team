# Conformance Test Conventions

A quick reference for `rtl-conformance-test`. Stays under 150 lines so it can be
consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Simulation output dir | `sim/conformance/` | per-run results |
| Vector input dir | `sim/conformance/vectors/` | `*.yuv`, `*.bin` |
| RTL output per vector | `sim/conformance/rtl_output_{id}.bin` | |
| JM/HM reference output | `sim/conformance/ref/{id}_jm_output.bin` | |
| Results file | `sim/conformance/results.json` | per-vector status |
| Comparison script | `skills/rtl-conformance-test/scripts/conformance_compare.py` | byte-exact diff |
| Stream metadata | `skills/rtl-conformance-test/templates/golden-metadata.json` | profile/level/version |
| DUT instance prefix | `u_dut` or `u_{module}` | `u_cabac_encoder` |
| TB input ports | `i_` prefix | `i_pixel_data` |
| TB output ports | `o_` prefix | `o_bitstream` |
| Clock | `clk` (single) or `{domain}_clk` | `sys_clk` |
| Reset | `rst_n` (single) or `{domain}_rst_n` (active-low async) | `sys_rst_n` |
| Type keyword | `logic` only (no `reg`/`wire`) | |

## 2. Output schema

### sim/conformance/results.json
```json
{
  "jm_hm_version": "JM 19.0",
  "standard": "H.264",
  "profile": "Baseline",
  "level": "4.1",
  "total_vectors": 500,
  "pass": 498,
  "fail": 2,
  "vectors": [
    {
      "id": "vec_001",
      "status": "PASS",
      "input": "sim/conformance/vectors/vec_001.yuv",
      "rtl_output": "sim/conformance/rtl_output_001.bin",
      "ref_output": "sim/conformance/ref/001_jm_output.bin"
    },
    {
      "id": "vec_024",
      "status": "FAIL",
      "divergence_byte": 1024,
      "expected_hex": "0x3A",
      "actual_hex":   "0x3B",
      "spec_section": "9.3.4.6"
    }
  ]
}
```

### golden-metadata.json (per stream)
```json
{
  "stream_id": "vec_001",
  "standard": "H.264",
  "profile": "High",
  "level": "4.1",
  "jm_version": "JM 19.0",
  "width": 1920,
  "height": 1080,
  "frame_count": 300
}
```

## 3. Comparison criteria

- **Bitexact** match is mandatory — no tolerance, no approximation.
  Any byte difference is a hard FAIL regardless of PSNR impact.
- JM 19.0 is the normative reference for H.264; HM 16.20 for H.265.
  Use ITU-T JVT conformance streams as the primary vector suite.
- Both encoder conformance (RTL encodes → JM decodes) and decoder conformance
  (JM encodes → RTL decodes) must be run when the design includes both paths.
- For decoder designs, also verify block-level conformance at each pipeline stage
  (CABAC, inverse TQ, prediction, reconstruction, deblocking, SAO) using C reference
  model output as the oracle — end-to-end comparison alone can mask stage-local bugs.
- Vectors can be parallelised — each vector runs in an independent simulation process.
- FAIL entries must record `divergence_byte`, `expected_hex`, and `actual_hex`; without
  these values the entry is non-actionable for debug.

## 4. Anti-patterns

- Accepting partial bitexact match ("498/500 pass") — codec standards require 100%;
  a partial pass means non-conformant.
- Using suffix convention in testbench (`data_i`, `clk_i`) — project uses prefix
  (`i_data`, `clk`). Bare `clk` is valid for single-domain designs.
- Running conformance before `conformance_report.json` from `ref-model` exists —
  the ref model gate must pass first.
- Tolerating `>10 vectors fail` without escalating to ref-model review —
  mass failures indicate a systemic issue, not a local RTL bug.
- Recording only PASS/FAIL without `divergence_byte`/`expected_hex`/`actual_hex`
  for failures — renders the result file useless for debug.
- Running conformance against the project's own C reference model (Phase 2 refC) —
  that is a self-test; always use the standard-body reference (JM/HM) or a vendor golden.
