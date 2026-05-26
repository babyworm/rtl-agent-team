# BFM Development Conventions

A quick reference for `bfm-develop`. Stays under 150 lines so it can be
consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Source files | `bfm/src/*.cpp`, headers in `bfm/src/*.h` | `bfm/src/cabac_bfm.cpp` |
| Module class | One `SC_MODULE` per architectural block | `SC_MODULE(CabacBfm)` |
| Port naming | Match `io_definition.json` exactly; use `i_`/`o_`/`io_` prefix | `i_pixel_data`, `o_bitstream` |
| Clock port | `clk` (single) or `{domain}_clk` | `sys_clk` |
| Reset port | `rst_n` (single) or `{domain}_rst_n` (active-low async) | `sys_rst_n` |
| Instance prefix | `u_` | `u_cabac_bfm` |
| Build dir | `bfm/build/` (CMake out-of-source) | `cmake .. && make` |
| Smoke test result | `bfm/smoke_test_result.txt` | `PASS latency=12ns` |
| Feature coverage | `reviews/phase-3-uarch/bfm-feature-coverage.md` | per-REQ-F-* table |
| Performance baseline | `bfm/perf_baseline.json` | per-block latency/throughput |
| C++ standard | C++17 | `-std=c++17` |

## 2. Output schema

### bfm/smoke_test_result.txt
```
PASS
transport=LT
latency=12ns
transactions=1
```

### bfm/perf_baseline.json
```json
{
  "tool": "SystemC TLM-2.0",
  "transport": "LT",
  "blocks": [
    {
      "name": "CabacBfm",
      "throughput_mbps": 320.0,
      "latency_ns": 12.0,
      "clock_cycles": 6
    }
  ]
}
```

### bfm-feature-coverage.md table
```
| REQ-F-* | Feature | BFM Module/Method | Ref Model Match | Status |
|---------|---------|-------------------|-----------------|--------|
| REQ-F-001 | Intra 4x4 | intra_pred_module::b_transport | intra_predict_4x4() | IMPLEMENTED |
| REQ-F-002 | Intra 8x8 | — | intra_predict_8x8() | MISSING |
```

## 3. Transport style & protocol rules

- **Default transport**: LT blocking (`b_transport`) — use for fast functional validation
  and I/O logging. Mandatory unless AT is explicitly requested.
- **AT non-blocking** (`nb_transport_fw`/`nb_transport_bw`): only when timing accuracy
  for pipelined or out-of-order behavior is explicitly required.
- **4-phase AT handshake**: `BEGIN_REQ → END_REQ → BEGIN_RESP → END_RESP` — all four
  phases must be present or AT simulation deadlocks.
- **AMBA protocol default**: AXI with `amba_pv::axi_extension`. Use AHB/APB/ACE only
  when architecture spec specifies them.
- **Memory Manager**: `tlm_mm_interface` required for payload pooling — prevents leaks
  during long simulation runs.
- **PEQ**: `peq_with_cb_and_phase` required for AT phase scheduling.
- **Cross-phase consistency**: BFM per-block functional output must match `refc/` output
  (shared test vectors, bitexact or within documented tolerance).

## 4. Anti-patterns

- Using LT for a performance BFM intended to model pipeline bubbles or OoO completions —
  LT cannot capture these; switch to AT.
- Omitting AMBA extensions — bus attributes (burst type, cache policy, protection) are lost.
- Omitting Memory Manager — payload leaks accumulate during multi-thousand-transaction runs.
- Port names that diverge from `io_definition.json` — breaks rtl-p5s-perf-verify compatibility.
- Skipping the smoke test — the build may succeed while the TLM binding is broken.
- Declaring feature coverage PASS based only on smoke test — structural check against
  `REQ-F-*` items is mandatory regardless of test pass/fail.
