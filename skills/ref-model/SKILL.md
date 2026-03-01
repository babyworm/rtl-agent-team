---
name: ref-model
description: "This skill should be used when building C functional reference models (no clock/reset) with external memory access abstraction and bitexact verification. DPI-C integration priority."
---

<Purpose>
Build a golden functional reference model in C that validates algorithm correctness.
This is NOT an RTL-style model — no clock, no reset, no cycle concept.
Inputs/outputs are function arguments. Internal state is variables/arrays.
External memory access is abstracted through dedicated access functions for bandwidth analysis.

Outputs: refc/*.c, refc/include/*.h, conformance_report.json.
Must achieve bitexact match against JM (H.264) or HM (H.265) reference software.
Runs in parallel with p2-arch-design during Phase 2.
</Purpose>

<Use_When>
- Phase 1 artifacts are complete and reference model does not exist
- Reference model needs update after spec change
- Conformance baseline is needed for RTL verification
- Bandwidth/datapath width exploration is needed
</Use_When>

<Do_Not_Use_When>
- Reference model already exists and conformance_report.json is current
- Only a quick algorithm question (use domain-consult instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL verification requires a golden reference. Writing the reference model before RTL
forces algorithm understanding and exposes spec ambiguities before silicon commitment.
Bitexact match against JM/HM is the industry standard acceptance criterion.

The model also serves as a bandwidth analysis tool: by tracking external memory access
counts and patterns through the abstraction layer, architects can estimate required
memory bandwidth before committing to hardware.

C is chosen over C++ for DPI-C compatibility — the model can be directly called from
SystemVerilog testbenches without wrapper overhead.
</Why_This_Exists>

<Execution_Policy>
- Relevant sub-domain expert(s) provide algorithm specification details (vcodec-syntax-entropy, vcodec-prediction, vcodec-transform-quant, or vcodec-filter-recon depending on the algorithm)
- ref-model-dev implements C model following functional model philosophy:
  - **No clock/reset**: Pure functional — call function, get result
  - **I/O as function arguments**: Inputs are const pointer params, outputs are pointer params
  - **Local memory = variables/arrays**: SRAM, register files → local arrays or struct members
  - **External memory = access function**: All external memory reads/writes go through `ext_mem_read()`/`ext_mem_write()` to track bandwidth
  - **Datapath width parameterizable**: `#define DATA_WIDTH`, `#define PARALLEL_LANES` to explore throughput
- Run JM/HM bitexact comparison as automated gate
- Gate fails if any test vector mismatches
</Execution_Policy>

<Steps>
1. Relevant sub-domain expert provides algorithm pseudocode and edge case table
2. ref-model-dev implements refc/*.c with clean C (no RTL bias, no clock/reset)
   - Function signatures: `void block_process(const input_t *in, output_t *out, context_t *ctx)`
   - Internal SRAM/registers: `ctx->sram[SIZE]`, `ctx->reg_field` (plain arrays/variables)
   - External memory: `ext_mem_read(addr, buf, size)` / `ext_mem_write(addr, buf, size)`
   - Datapath width: `#define PARALLEL_LANES 4` — process N elements per call, adjustable
   - C coding conventions: snake_case, stdint.h types, C11 standard
   - DPI-C compatible: no C++ features (no classes, no templates, no exceptions)
3. Build ref model via Bash CLI: `cd refc && make build`
4. Run bitexact comparison via Bash CLI: `cd refc && make test`
5. Run bandwidth analysis: `cd refc && make bandwidth` (reports ext_mem access count/pattern)
6. Fix any mismatches (iterate until all vectors pass)
7. Write conformance_report.json with pass/fail per vector and JM/HM version
8. Write bandwidth_report.json with external memory access statistics per block
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:vcodec-syntax-entropy-expert",
     prompt="Provide algorithm pseudocode and edge case table for CABAC entropy coding per H.264 spec section 9.3.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Implement C functional reference model at refc/. Must be bitexact vs JM. "
            "No clock/reset — pure functional model. I/O as function arguments. "
            "Internal memory as arrays/variables. External memory via ext_mem_read/write functions. "
            "Datapath width parameterizable via PARALLEL_LANES define. "
            "C11, DPI-C compatible (no C++ features). Follow C coding conventions.")

# Build and test via Bash CLI (NOT MCP)
Bash: cd refc && make build          # gcc -std=c11 -Wall -Wextra -Werror
Bash: cd refc && make test           # bitexact comparison
Bash: cd refc && make bandwidth      # external memory access analysis
Bash: cd refc && make sanitize       # run with -fsanitize=address,undefined
```
</Tool_Usage>

<Examples>
<Good>
ref-model-dev implements CABAC coder as pure C function:
```c
void cabac_encode(const cabac_input_t *in, cabac_output_t *out, cabac_ctx_t *ctx) {
    // Internal context table — local array (models SRAM)
    uint8_t context_table[460];
    // External memory read for bitstream buffer
    ext_mem_read(ctx->bitstream_addr, ctx->read_buf, 64);
    // Process with PARALLEL_LANES bins per call
    for (int i = 0; i < PARALLEL_LANES; i++) { ... }
    // External memory write for encoded output
    ext_mem_write(ctx->output_addr, out->encoded, out->num_bytes);
}
```
Bitexact test runs 500 vectors against JM 19.0; all pass.
Bandwidth report shows 2.3 MB/frame external memory reads, 0.8 MB/frame writes.
</Good>
<Bad>
Implementing ref model with clock/reset and cycle-accurate step function —
this is Phase 3 BFM territory, not Phase 2 functional model.
The purpose here is algorithm correctness and bandwidth estimation, not timing.
</Bad>
<Bad>
Using C++ classes and templates — breaks DPI-C compatibility and adds
unnecessary complexity for a functional model.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Bitexact mismatch persists after 3 fix iterations → report failing vectors to user with diff
- JM/HM not available in environment → halt and instruct user to install
- External memory bandwidth exceeds technology limits → escalate to arch-designer for block restructuring
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] refc/*.c compiles cleanly with `gcc -std=c11 -Wall -Wextra -Werror`
- [ ] No C++ features used (DPI-C compatible pure C)
- [ ] No clock/reset in model — pure functional
- [ ] External memory access uses ext_mem_read/ext_mem_write abstraction
- [ ] PARALLEL_LANES parameterizable for datapath width exploration
- [ ] All test vectors pass bitexact comparison vs JM/HM
- [ ] conformance_report.json written with JM/HM version and vector results
- [ ] bandwidth_report.json written with external memory access statistics
</Final_Checklist>

<Advanced>
Use JM 19.0 for H.264, HM 16.20 for H.265. Test vector set: ITU-T conformance streams.
Reference model must be free of undefined behavior (run with -fsanitize=address,undefined).

External memory access function signature:
```c
// Track every external memory access for bandwidth analysis
typedef struct {
    uint64_t total_reads;
    uint64_t total_writes;
    uint64_t total_read_bytes;
    uint64_t total_write_bytes;
} ext_mem_stats_t;

void ext_mem_read(uint32_t addr, void *buf, uint32_t size);
void ext_mem_write(uint32_t addr, const void *buf, uint32_t size);
ext_mem_stats_t ext_mem_get_stats(void);
void ext_mem_reset_stats(void);
```

Datapath width exploration: run the model with PARALLEL_LANES=1,2,4,8 and compare
bandwidth_report.json to find the optimal balance between throughput and memory bandwidth.
</Advanced>
