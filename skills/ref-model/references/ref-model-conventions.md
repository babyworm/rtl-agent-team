# Reference Model Conventions

A quick reference for `ref-model`. Stays under 150 lines so it can be
consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Source files | `refc/*.c`, headers in `refc/include/*.h` | `refc/cabac_encoder.c` |
| Function signature | `void block_fn(const input_t *in, output_t *out, context_t *ctx)` | `void cabac_encode(...)` |
| Internal SRAM/reg | struct member arrays or local arrays | `ctx->sram[SIZE]` |
| External memory | `ext_mem_read()` / `ext_mem_write()` only | never bare `malloc` for bus traffic |
| Datapath width | `#define PARALLEL_LANES N` (1/2/4/8) | `PARALLEL_LANES 4` |
| Bandwidth stats | `ext_mem_stats_t` from `ext_mem_get_stats()` | `stats.total_read_bytes` |
| Conformance report | `conformance_report.json` | at project root |
| Bandwidth report | `bandwidth_report.json` | at project root |
| Feature coverage | `reviews/phase-2-architecture/ref-model-feature-coverage.md` | per-REQ-F-* table |
| C standard | C11 (`-std=c11`) | `gcc -std=c11 -Wall -Wextra -Werror` |
| Identifier style | `snake_case` for functions/vars; `UPPER_SNAKE_CASE` for macros/defines | |

## 2. Output schema

### conformance_report.json
```json
{
  "jm_hm_version": "JM 19.0",
  "total_vectors": 500,
  "pass": 500,
  "fail": 0,
  "vectors": [
    {"id": "vec_001", "status": "PASS", "input": "...", "ref_output": "..."}
  ]
}
```

### bandwidth_report.json
```json
{
  "parallel_lanes": 4,
  "blocks": [
    {
      "name": "cabac_encode",
      "total_reads": 12340,
      "total_read_bytes": 789120,
      "total_writes": 3210,
      "total_write_bytes": 205440,
      "estimated_read_cycles": 6170000,
      "estimated_write_cycles": 1605000
    }
  ]
}
```
Latency defaults: `MEM_LATENCY_INTERNAL=1`, `MEM_LATENCY_EXTERNAL=500`.

### ref-model-feature-coverage.md table
```
| REQ-F-* | Feature | Ref Model Function/Path | Status |
|---------|---------|------------------------|--------|
| REQ-F-001 | Intra 4x4 pred | intra_predict_4x4() | IMPLEMENTED |
| REQ-F-002 | Intra 8x8 pred | — | MISSING |
```

## 3. Length / fidelity guidance

- **No clock, no reset**: the model is a pure function — call it, get a result.
- **DPI-C compatible**: no C++ features (no classes, templates, exceptions, STL).
  The model must compile as plain C11 for direct SV testbench linkage.
- **External memory access function signature** (fixed — do not change):
  ```c
  void ext_mem_read(uint32_t addr, void *buf, uint32_t size);
  void ext_mem_write(uint32_t addr, const void *buf, uint32_t size);
  ext_mem_stats_t ext_mem_get_stats(void);
  void ext_mem_reset_stats(void);
  ```
- **JM/HM versions**: JM 19.0 for H.264; HM 16.20 for H.265. Use ITU-T conformance streams.
- **Sanitizers**: always run with `-fsanitize=address,undefined` before declaring gate pass.
- Feature coverage: 100% of `REQ-F-*` items must map to a real code path (structural check,
  not just bitexact test coverage).

## 4. Anti-patterns

- Writing a clock/reset-driven step function — that is Phase 3 BFM territory.
- Using C++ (classes, templates, `new`/`delete`) — breaks DPI-C compatibility.
- Accessing external memory directly (e.g., global arrays) instead of `ext_mem_read/write` —
  hides bandwidth from analysis.
- Declaring feature coverage PASS based only on bitexact test pass — bitexact tests may
  not exercise all REQ-F-* branches.
- Inventing conformance numbers — always run the actual JM/HM comparison, never estimate.
