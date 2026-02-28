---
name: rtl-sv-unit-test
description: "Tier 2 unit testing: verify each RTL module against its uarch specification and C reference model. Goes beyond Tier 1 smoke to exercise FSM transitions, pipeline behavior, and data transformations."
---

<Purpose>
Write and run unit tests that verify each RTL module implements its microarchitecture
specification correctly. Compares RTL output against the C reference model for functional
correctness. Goes beyond Tier 1 smoke testing (rtl-code Wave 4) to exercise key features
at uarch level: FSM state transitions, pipeline stage behavior, data transformation accuracy.

**Testing Tier Context:**
```
Tier 1: Smoke Test     — connectivity, R/W, basic ops (rtl-code Wave 4)
Tier 2: Unit Test      — reference comparison, uarch features (THIS SKILL) ←
Tier 3: Module Regr.   — cocotb multi-seed (rtl-func-verify)
Tier 4: Integration    — cross-module, end-to-end (rtl-integration-test)
```

Outputs: sim/{module}/tb_{module}.sv testbench files + sim/{module}/{module}_unit_results.json.
</Purpose>

<Use_When>
- Phase 4 RTL is lint-clean AND Tier 1 smoke test passed (rtl-code Wave 4)
- Each module needs uarch-level functional verification with reference comparison
- A new module's key features need targeted testing beyond connectivity
- A bug fix needs regression test verifying the fix against reference model
</Use_When>

<Do_Not_Use_When>
- Only basic connectivity/R/W verification needed (covered by rtl-code Wave 4 smoke — Tier 1)
- Full multi-seed regression needed (use rtl-func-verify — Tier 3)
- Integration/cross-module testing (use rtl-integration-test — Tier 4)
- Formal verification preferred (use rtl-sva-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
Tier 1 (smoke) only verifies connectivity and basic I/O. Tier 2 unit tests verify that each
module implements its uarch spec — FSM states, pipeline stages, data transformations — using
the C reference model as the golden oracle. This catches behavioral bugs that smoke tests miss,
while remaining faster and more targeted than full regression (Tier 3).
</Why_This_Exists>

<Coding_Convention_Requirements>
Testbenches MUST follow the project coding conventions (CLAUDE.md):
- Port connections: `i_` prefix for inputs, `o_` prefix for outputs, `io_` for bidirectional
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Use `logic` only (NOT `reg`/`wire`)
- DUT instance: `u_` prefix (e.g., `u_dut`)
- Testbench filename: `tb_{module}.sv` (e.g., `tb_cabac_encoder.sv`)
</Coding_Convention_Requirements>

<Execution_Policy>
- testbench-dev writes SV testbenches per module (parallel), targeting uarch features
- Reference model comparison: Mode A (DPI-C) or Mode B (file compare) — auto-selected
- func-verifier runs simulations via run_sim.sh and reports results
- Failing tests trigger waveform analysis before reporting
- Gate: all unit tests pass AND reference comparison has zero mismatches
</Execution_Policy>

<Steps>
1. Read uarch/{module}.md to extract key features to test:
   - FSM states and transitions
   - Pipeline stage behavior (latency, throughput)
   - Data transformation correctness (arithmetic, encoding, etc.)
   - Handshake protocols (valid/ready)

2. testbench-dev writes sim/{module}/tb_{module}.sv for each module (parallel):
   - Use `templates/sv-testbench-template.sv` as scaffold
   - DUT instantiated as `u_dut` with correct `i_`/`o_` port connections
   - Clock generated as `sys_clk` (or appropriate domain clock)
   - Reset generated as `sys_rst_n` (active-low)
   - Test cases target uarch-specified behavior (not just connectivity)
   - Each uarch feature gets at least one dedicated test case

3. Reference model comparison (two modes, auto-selected):

   **Mode A: DPI-C (when verilator and DPI .so available)**
   - refc/{module}_ref.c functions imported via DPI-C
   - SV TB directly calls reference functions for cycle-level comparison
   - Compile:
     ```bash
     scripts/run_sim.sh --sim verilator --top tb_{module} --outdir sim/{module} --trace \
       --dpi refc/build/lib{module}_ref.so \
       rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv
     ```

   **Mode B: File Compare (iverilog or when DPI-C unavailable)**
   - RTL sim → output file (sim/{module}/{module}_rtl_out.txt)
   - ref_model binary → output file (sim/{module}/{module}_ref_out.txt)
   - `diff` or byte-by-byte comparison
   - Compile:
     ```bash
     scripts/run_sim.sh --sim iverilog --top tb_{module} --outdir sim/{module} --trace \
       rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv
     ```

   Mode auto-selection: refc/build/lib{module}_ref.so exists → Mode A, else → Mode B

4. Per-feature test execution:
   - Each uarch feature gets at least 1 test case
   - Pass/fail tracked per feature, not just per module
   - On failure: waveform-analyzer reviews .vcd, identifies bug location

5. Results: sim/{module}/{module}_unit_results.json
   ```json
   {
     "module": "{module}",
     "tier": 2,
     "ref_mode": "A_DPI" | "B_FILE",
     "features": [
       {"name": "fsm_idle_to_active", "status": "PASS"},
       {"name": "pipeline_latency_3cyc", "status": "PASS"},
       {"name": "transform_accuracy", "status": "FAIL", "mismatch_cycle": 47}
     ],
     "ref_mismatches": 0,
     "pass_count": 5,
     "fail_count": 0,
     "total": 5
   }
   ```

6. Report pass/fail summary with per-feature details and reference comparison status
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 2: Write Tier 2 testbenches (parallel, one per module)
# ============================================================
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write Tier 2 SV unit testbench sim/cabac_encoder/tb_cabac_encoder.sv for rtl/cabac_encoder/cabac_encoder.sv. Use templates/sv-testbench-template.sv as scaffold. Read uarch/cabac_encoder.md to identify key features: FSM states, pipeline stages, data transforms. Write at least 1 test case per uarch feature. Use sys_clk/sys_rst_n, i_/o_ port prefixes, u_dut instance name.")

# ============================================================
# Step 3A: DPI-C reference comparison (verilator)
# ============================================================
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run Tier 2 unit test via run_sim.sh: scripts/run_sim.sh --sim verilator --top tb_cabac_encoder --outdir sim/cabac_encoder --trace --dpi refc/build/libcabac_encoder_ref.so rtl/cabac_encoder/cabac_encoder.sv sim/cabac_encoder/tb_cabac_encoder.sv. Report pass/fail per feature and reference mismatches.")

# ============================================================
# Step 3B: File-based reference comparison (iverilog fallback)
# ============================================================
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run Tier 2 unit test: (1) refc/build/cabac_encoder_ref --input test_vectors.txt --output sim/{module}/cabac_encoder_ref_out.txt (2) scripts/run_sim.sh --sim iverilog --top tb_cabac_encoder --outdir sim/cabac_encoder --trace rtl/cabac_encoder/cabac_encoder.sv sim/cabac_encoder/tb_cabac_encoder.sv (3) diff sim/{module}/cabac_encoder_ref_out.txt sim/{module}/cabac_encoder_rtl_out.txt. Report per-feature pass/fail and mismatches.")

# ============================================================
# Waveform analysis on failure
# ============================================================
Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/{module}/tb_cabac_encoder.vcd. Identify root cause of unit test failure at failing assertion. Compare RTL signals against expected reference behavior.")
```
</Tool_Usage>

<Examples>
<Good>
6 modules, 6 testbenches written in parallel; each targets 3-5 uarch features from uarch/*.md;
all use `sys_clk`/`sys_rst_n` and `i_`/`o_` port naming; reference comparison via DPI-C (Mode A);
5 modules pass all features; 1 module fails FSM transition test (missing FLUSH state);
waveform shows state register not updated on bypass path; RTL fix applied; retest passes;
sim/{module}/*_unit_results.json produced for all modules with per-feature status.
</Good>
<Bad>
Writing a single monolithic testbench for the entire design — hard to isolate failures and debug.
Using `clk`, `rst_n`, `data_i` instead of `sys_clk`, `sys_rst_n`, `i_data` — violates project conventions.
Only testing connectivity (reset + basic I/O) without targeting uarch features — that's Tier 1, not Tier 2.
Running iverilog directly instead of using run_sim.sh — loses simulator portability.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Module fails unit test and waveform analysis cannot identify root cause → escalate to rtl-architect
- Simulator not available → report to user, suggest installation or Docker EDA image
- Testbench uses wrong naming convention → testbench-dev must rewrite before simulation
- Reference model not available → fall back to self-checking TB (reduced confidence), flag to user
- Reference mismatches persist after RTL fix → escalate to ref-model-dev for model review
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] sim/{module}/tb_{module}.sv exists for every module
- [ ] All testbenches use `i_`/`o_` port prefixes, `sys_clk`/`sys_rst_n`, `u_dut`
- [ ] Each uarch feature has at least one test case
- [ ] Reference model comparison executed (DPI-C or file-based)
- [ ] Zero mismatches between RTL and reference model
- [ ] sim/{module}/{module}_unit_results.json produced with per-feature status
- [ ] All simulations compile and complete without crashes
- [ ] All unit tests pass
- [ ] Failure analysis done for any initial failures
- [ ] run_sim.sh used (not direct iverilog/verilator invocation)
</Final_Checklist>

<Advanced>
Testbenches should use $dumpvars for waveform capture even on passing tests (for coverage).
Randomize input sequences with $urandom for broader coverage within unit test time budget.
Use `always_ff`, `always_comb` in testbench helper modules (never `always @*`).

**DPI-C Mode A setup (verilator):**
```bash
# Build reference model as shared library
cd refc && mkdir -p build
gcc -std=c11 -shared -fPIC -o build/lib{module}_ref.so src/{module}_ref.c
```

**Reference comparison modes:**
- Mode A (DPI-C): Fastest, cycle-accurate, requires verilator + .so build
- Mode B (file): Portable, works with any simulator, requires ref_model binary

**Tier transition rules:**
- Tier 1 PASS (rtl-code Wave 4) → Tier 2 eligible
- Tier 2 PASS (this skill) → Tier 3 eligible (rtl-func-verify)
- Tier 2 FAIL → fix at rtl-bugfix, re-run Tier 2
</Advanced>
