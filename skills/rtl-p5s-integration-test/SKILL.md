---
name: rtl-p5s-integration-test
description: "Tier 4 integration testing: full system-level verification of cross-module data flow, reset propagation, clock connectivity, and end-to-end scenarios."
---

<Purpose>
Run integration-level tests on the complete RTL system. Verifies that modules work
correctly together: data flows through the pipeline end-to-end, reset propagates
to all sub-modules, clocks are connected correctly, and handshake protocols work
across module boundaries. This is Tier 4 testing — runs after Tier 2 (unit) and
Tier 3 (module regression) pass.

**Testing Tier Context:**
```
Tier 1: Smoke Test     — connectivity, R/W, basic ops (rtl-p4-implement Wave 4)
Tier 2: Unit Test      — reference comparison, uarch features (rtl-p4s-unit-test)
Tier 3: Module Regr.   — cocotb multi-seed (rtl-p5s-func-verify)
Tier 4: Integration    — cross-module, end-to-end (THIS SKILL) ←
```

Outputs: sim/top/integration_results.json + sim/top/ test files.
</Purpose>

<Use_When>
- All modules pass Tier 2 unit tests and Tier 3 module regression
- Need to verify cross-module interactions
- Phase 5 integration verification
- Top-level system-level test before final compliance
- After multi-module RTL changes that may affect interfaces
</Use_When>

<Do_Not_Use_When>
- Individual modules still failing unit tests (fix at Tier 2 first)
- Only need single-module regression (use rtl-p5s-func-verify — Tier 3)
- Performance measurement (use rtl-p5s-perf-verify)
- Standards conformance bitexact testing (use rtl-conformance-test)
</Do_Not_Use_When>

<Why_This_Exists>
Modules that pass individually may fail when connected due to interface mismatches,
protocol violations, or timing assumptions that don't hold across boundaries.
Integration testing catches: width mismatches at module boundaries, reset not propagating
to all sub-modules, backpressure not flowing through the pipeline, and data corruption
at interface handoff points. These bugs are invisible to per-module testing.
</Why_This_Exists>

<Coding_Convention_Requirements>
Integration testbenches MUST follow project conventions (CLAUDE.md):
- Port connections: `i_` prefix for inputs, `o_` prefix for outputs
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- DUT instance: `u_dut` for top-level, `u_` prefix for sub-modules
- Use `logic` only (NOT `reg`/`wire`)
- cocotb signals: `dut.sys_clk`, `dut.i_*`, `dut.o_*`
</Coding_Convention_Requirements>

<Execution_Policy>
- integration-verifier validates structural connectivity first (static checks)
- testbench-dev writes integration TBs (SV or cocotb, depending on complexity)
- eda-runner runs simulation via run_sim.sh (SV TB) or cocotb Makefile
- End-to-end reference comparison: full-system ref_model output vs RTL output
- waveform-analyzer debugs any cross-module failures
- Gate: all connectivity checks PASS AND data flow tests PASS AND handshake tests PASS
</Execution_Policy>

<Steps>
1. Read architecture.md and io_definition.json for system-level interface spec
2. Read top-level module to map all module interconnections

3. **Connectivity Verification (static):**
   - integration-verifier checks:
     - Reset propagation: verify sys_rst_n reaches all sub-modules
     - Clock connectivity: verify all modules receive correct clock
     - Port width matching: verify no width mismatches at boundaries
     - Signal naming consistency across module boundaries

4. **Data Flow Tests (end-to-end):**
   - testbench-dev writes integration TB:
     - SV TB: `sim/top/tb_{top}_integration.sv`
     - cocotb: `sim/top/test_{top}_integration.py`
   - Input → full pipeline → output, compare with reference
   - Test representative scenarios from requirements.json
   - Verify data integrity through each pipeline stage

5. **Handshake Protocol Tests:**
   - valid/ready backpressure propagation across modules
   - Stall and resume behavior at module boundaries
   - Corner cases:
     - Simultaneous backpressure from multiple consumers
     - Pipeline flush propagation
     - Back-to-back transactions without gaps
     - Starvation scenarios (one port starving another)

6. **Simulation:**
   - SV TB:
     ```bash
     scripts/run_sim.sh --sim verilator --top tb_{top}_integration \
       --filelist rtl/filelist_top.f --outdir sim/top --trace \
       sim/top/tb_{top}_integration.sv
     ```
   - cocotb:
     ```bash
     make -C sim/top SIM=verilator TOPLEVEL={top} MODULE=test_{top}_integration
     ```
   - Fallback (iverilog — for 4-state X/Z simulation or verilator-unsupported constructs):
     ```bash
     scripts/run_sim.sh --sim iverilog --top tb_{top}_integration \
       --filelist rtl/filelist_top.f --outdir sim/top --trace \
       sim/top/tb_{top}_integration.sv
     make -C sim/top SIM=icarus TOPLEVEL={top} MODULE=test_{top}_integration
     ```

7. **End-to-end reference comparison:**
   - Full system input → ref_model → expected output
   - RTL sim → actual output
   - Byte-by-byte comparison: `diff` or custom comparator
   - On mismatch: waveform-analyzer identifies divergence point and pipeline stage

8. Report: sim/top/integration_results.json
   ```json
   {
     "top_module": "{top}",
     "tier": 4,
     "connectivity": {
       "reset_propagation": "PASS",
       "clock_connectivity": "PASS",
       "port_width_match": "PASS"
     },
     "data_flow": [
       {"scenario": "basic_forward", "status": "PASS"},
       {"scenario": "max_throughput", "status": "PASS"}
     ],
     "handshake": [
       {"test": "backpressure_propagation", "status": "PASS"},
       {"test": "pipeline_flush", "status": "PASS"}
     ],
     "e2e_reference": "PASS",
     "verdict": "PASS"
   }
   ```
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 3: Connectivity Verification (static)
# ============================================================
Task(subagent_type="rtl-agent-team:integration-verifier",
     prompt="Verify structural connectivity of top-level module. Check: (1) reset propagation — sys_rst_n reaches all sub-modules, (2) clock connectivity — all modules receive correct clock, (3) port width matching — no width mismatches at boundaries. Read rtl/*/*.sv and architecture.md.")

# ============================================================
# Step 4-5: Integration TB (SV or cocotb)
# ============================================================
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write integration testbench sim/top/tb_{top}_integration.sv (or sim/top/test_{top}_integration.py). Test: (1) end-to-end data flow through full pipeline, (2) backpressure propagation across module boundaries, (3) pipeline flush, (4) back-to-back transactions. Use sys_clk/sys_rst_n, i_/o_ port naming, u_dut instance.")

# ============================================================
# Step 6: Simulation
# ============================================================
# SV TB path
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run integration test: scripts/run_sim.sh --sim verilator --top tb_{top}_integration --filelist rtl/filelist_top.f --outdir sim/top --trace sim/top/tb_{top}_integration.sv. Report pass/fail per test category.")

# cocotb path
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb integration test: make -C sim/top SIM=verilator TOPLEVEL={top} MODULE=test_{top}_integration. Report pass/fail per test.")

# ============================================================
# Step 7: End-to-end reference comparison
# ============================================================
Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Run end-to-end reference comparison: (1) refc/build/{top}_ref --input test_vectors/ --output sim/top/ref_out.bin (2) Compare with RTL output sim/top/rtl_out.bin. Report byte-by-byte match status.")

# ============================================================
# Waveform debug on failure
# ============================================================
Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/top/tb_{top}_integration.vcd. Identify cross-module failure: trace signal from output back through pipeline stages to find the originating module and divergence cycle.")
```
</Tool_Usage>

<Examples>
<Good>
Integration test on 6-module pipeline:
  Connectivity: reset/clock/width all PASS (static check in 2 seconds);
  Data flow: 5 end-to-end scenarios tested, all PASS;
  Handshake: backpressure test reveals module_c not propagating o_ready to module_b;
  waveform-analyzer identifies missing wire in module_c port map;
  RTL fix applied via rtl-p4s-bugfix; retest all PASS;
  End-to-end ref comparison: byte-exact match.
</Good>
<Bad>
Running integration test when individual modules still fail unit tests — integration failures
mask the real per-module bugs and make debugging much harder.
Testing only happy-path data flow without backpressure or stall scenarios — misses the most
common class of integration bugs.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Connectivity check fails (width mismatch, missing connection) → rtl-coder must fix before sim
- End-to-end reference mismatch → waveform-analyzer + func-verifier isolate to specific module → Tier 2 retest
- Handshake protocol violation detected → protocol-checker for detailed analysis
- Cross-module timing issue → timing-advisor for pipeline analysis
- More than 3 integration bugs found → escalate to rtl-architect for interface review
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Connectivity check passed (reset propagation, clock, port widths)
- [ ] Integration TB written (SV or cocotb)
- [ ] End-to-end data flow tests executed
- [ ] Handshake/backpressure tests executed
- [ ] End-to-end reference comparison done (byte-by-byte)
- [ ] sim/top/integration_results.json produced
- [ ] All integration tests PASS
- [ ] run_sim.sh used for SV TB simulation
- [ ] Waveform analysis done for any failures
</Final_Checklist>

<Advanced>
**Integration test ordering:**
1. Static connectivity checks first (fast, catches obvious wiring bugs)
2. Simple data flow (single transaction end-to-end)
3. Sustained throughput (back-to-back transactions)
4. Backpressure and stall scenarios
5. Error injection and recovery

**Multi-clock domain integration:**
- Verify CDC synchronizers are connected correctly
- Test data transfer across clock domains
- Use rtl-p5s-cdc-verify for detailed CDC analysis

**Tier transition rules:**
- Tier 3 PASS (rtl-p5s-func-verify) → Tier 4 eligible
- Tier 4 PASS (this skill) → Phase 5 final compliance eligible
- Tier 4 FAIL → isolate to module, fix via rtl-p4s-bugfix, retest Tier 2→3→4
</Advanced>
