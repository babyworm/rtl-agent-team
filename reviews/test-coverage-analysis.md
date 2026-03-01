# Test Coverage Analysis

- Date: 2026-03-01
- Reviewer: coverage-analyst
- Scope: Full codebase test coverage audit
- Verdict: SIGNIFICANT GAPS — multiple areas require test development

---

## 1. Executive Summary

The RTL Agent Team project is a comprehensive 50-agent, 40-skill Claude Code plugin for automated RTL design and verification. It defines a rigorous 4-tier testing hierarchy, extensive simulation infrastructure, and coverage tooling — but **the actual test implementation lags far behind the framework's capabilities**. The project currently has:

- **1 RTL source module** (`h264_hadamard4x4.sv`, 164 lines)
- **2 iverilog-compatible shims** (compatibility wrappers, not tests)
- **0 actual testbenches** (no `tb_*.sv`, no `test_*.py`, no cocotb tests)
- **0 coverage data** (no `coverage.dat`, no `merged.info`, no HTML reports)
- **0 formal verification files** (no SVA properties, no SymbiYosys configs)
- **0 reference model implementations** (no C/C++ golden model in `refc/`)

The design note (`reviews/phase-6-review/design-note.md`) references a broader H.264 TQ subsystem with 7 modules and 62 unit tests, but those artifacts are not present in the repository. Only the Hadamard 4x4 module and its iverilog shims exist.

---

## 2. Inventory of What Exists

### 2.1 RTL Source Code

| File | Lines | Description |
|------|-------|-------------|
| `rtl/src/h264_hadamard4x4.sv` | 164 | 2-stage pipelined 4x4 Hadamard transform (SystemVerilog) |

### 2.2 Testbench/Shim Files

| File | Lines | Type | Is an Actual Test? |
|------|-------|------|--------------------|
| `tb/unit/shims/h264_hadamard4x4.sv` | 262 | iverilog-compatible shim | **No** — functionally identical RTL rewrite, no stimulus/checker |
| `tb/unit/shims/h264_hadamard2x2.sv` | 92 | iverilog-compatible shim | **No** — shim for a module not in `rtl/src/` |

### 2.3 Test Infrastructure (exists but unused)

| Component | Location | Status |
|-----------|----------|--------|
| `run_sim.sh` | `scripts/run_sim.sh` | Implemented (403 lines, 5-simulator support) — never invoked |
| `run_regression.sh` | `skills/rtl-regression-run/scripts/run_regression.sh` | Implemented — no tests to run |
| `merge_coverage.sh` | `skills/rtl-regression-run/scripts/merge_coverage.sh` | Implemented — no coverage data to merge |
| `check_conventions.sh` | `skills/rtl-lint-check/scripts/check_conventions.sh` | Implemented — available but no CI integration |
| cocotb test template | `skills/rtl-func-verify/templates/cocotb-test-template.py` | Template only, not instantiated |
| SV testbench template | `skills/rtl-sv-unit-test/templates/sv-testbench-template.sv` | Template only, not instantiated |
| UVM templates | `skills/rtl-uvm-verify/templates/` | Templates only |

### 2.4 Reference Models

| Expected | Status |
|----------|--------|
| `refc/src/` or `refc/h264_hadamard4x4/` | **Missing** — no C reference model |
| `refc/build/` (DPI-C `.so`) | **Missing** |
| `refc/test/` (ref model unit tests) | **Missing** |
| `refc/vectors/` (test vectors) | **Missing** |

### 2.5 Coverage Data

| Expected | Status |
|----------|--------|
| `sim/coverage/merged.info` | **Missing** |
| `sim/coverage/html/` | **Missing** |
| `sim/coverage/coverage_gaps.md` | **Missing** |
| Any `.dat` or `.info` files | **Missing** |

---

## 3. Gap Analysis by Testing Tier

### Tier 1: Smoke Tests — MISSING

**Expected:** `sim/h264_hadamard4x4/tb_h264_hadamard4x4_smoke.sv`

**What should be tested:**
- Reset behavior (active-low async reset clears `o_valid`, `o_block`)
- Basic connectivity (input feeds through pipeline, output appears)
- Single transaction: drive `i_valid` with known input, observe `o_valid` after pipeline latency
- Handshake: `o_ready` asserted when pipeline is empty
- Forward mode (`i_mode=0`) produces any non-X output
- Inverse mode (`i_mode=1`) produces any non-X output

**Priority: HIGH** — This is the minimum viable test and a prerequisite for all other tiers.

### Tier 2: Unit Tests — MISSING

**Expected:** `sim/h264_hadamard4x4/tb_h264_hadamard4x4.sv`

**What should be tested against a reference model:**
- **Forward Hadamard correctness:** For known 4x4 input matrices, verify output matches the mathematical definition `H * X * H^T` (butterfly decomposition)
- **Inverse Hadamard correctness:** Verify `(H * X * H^T) >>> 1` normalization
- **Round-trip consistency:** Forward followed by inverse should approximate the original input (with known truncation loss)
- **Edge cases:**
  - All-zero input matrix
  - All-max positive input (`16'h7FFF` with default `DATA_WIDTH=16`)
  - All-max negative input (`16'h8000`)
  - Single non-zero element in each position (impulse response)
  - Alternating positive/negative pattern
- **Pipeline behavior:**
  - Back-to-back transactions (consecutive `i_valid` assertions)
  - Pipeline stall when downstream is not ready (`i_ready=0`)
  - Stall release: data correctness preserved after stall
  - Mode switching between forward and inverse on consecutive transactions
- **Parameter variation:** `DATA_WIDTH` values other than 16 (e.g., 8, 12)

**Priority: HIGH** — Required before Tier 3 and critical for functional correctness.

### Tier 3: Module Regression (cocotb) — MISSING

**Expected:** `sim/h264_hadamard4x4/test_h264_hadamard4x4.py` + `Makefile`

**What should be tested:**
- **Multi-seed random testing:** 5+ seeds with random 4x4 input matrices, comparing against a Python reference Hadamard implementation
- **Backpressure randomization:** Random `i_ready` deassertion patterns
- **Input flow control:** Random gaps between `i_valid` assertions
- **Functional coverage points:**
  - `i_mode` toggled (forward and inverse both exercised)
  - All 16 matrix positions driven with both positive and negative values
  - Pipeline full/empty/partial states
  - Stall and resume transitions
- **Coverage targets:** line >= 90%, toggle >= 80%, FSM >= 70%

**Priority: MEDIUM** — Depends on Tier 2 passing first.

### Tier 4: Integration Tests — NOT APPLICABLE YET

Only one module exists in `rtl/src/`, so integration testing is not yet meaningful. When additional TQ subsystem modules are added (DCT, quantizer, dequantizer, etc.), integration tests should verify end-to-end data flow.

---

## 4. Gap Analysis by Verification Category

### 4.1 Lint — PARTIALLY DONE (inferred from design note)

The design note mentions lint passing, but no lint reports exist in the repo:
- **Missing:** `lint/reports/h264_hadamard4x4_lint.txt`
- **Missing:** `reviews/phase-4-rtl/lint-report.md`
- **Action:** Run `verilator --lint-only -Wall rtl/src/h264_hadamard4x4.sv` and capture results

### 4.2 Formal Verification (SVA) — MISSING

**Expected:** `sim/formal/h264_hadamard4x4_sva.sv` + `sim/formal/h264_hadamard4x4.sby`

**Properties that should be asserted:**
- **Handshake protocol:**
  - `o_valid` never asserted in reset
  - `o_valid` stays high until `i_ready` is asserted (no data loss)
  - `o_ready` reflects pipeline capacity correctly
  - No data output without prior valid input
- **Pipeline invariants:**
  - `valid_s1` is never X after reset
  - Output data is stable while `o_valid && !i_ready` (no glitching)
  - Pipeline latency is exactly 2 cycles (row + column + output register)
- **Arithmetic safety:**
  - Intermediate widths (`L_EXT_WIDTH=18`, `L_COL_WIDTH=20`) never overflow for `DATA_WIDTH=16` inputs
- **Liveness:**
  - If `i_valid` and `o_ready`, then `o_valid` eventually asserts (no deadlock)

**Priority: MEDIUM** — Catches subtle protocol and liveness bugs that simulation may miss.

### 4.3 CDC Analysis — NOT APPLICABLE

The design is single clock domain (`sys_clk`), so CDC analysis is not required for the current module.

### 4.4 Reference Model — MISSING

A C reference model for the 4x4 Hadamard transform is needed for Tier 2 comparisons:

**Expected:** `refc/src/hadamard4x4.c` + `refc/include/hadamard4x4.h`

**Requirements:**
- Pure C11 implementation (no clock/reset, functional model only)
- Forward: `H * X * H^T` with truncation to `DATA_WIDTH`
- Inverse: `(H * X * H^T) >>> 1` normalization
- Matching I/O data types (signed 16-bit elements, 4x4 matrix)
- DPI-C compatible for Verilator co-simulation

**Priority: HIGH** — The 4-tier test strategy explicitly requires a reference model before writing testbenches (CLAUDE.md absolute rule #2).

### 4.5 Synthesis Estimation — MISSING

**Expected:** `syn/reports/h264_hadamard4x4_synth.txt`

**Action:** Run Yosys synthesis to get area/timing estimates and verify no latches are inferred.

---

## 5. Known RTL Issues (from Design Note) Requiring Test Coverage

The Phase 6 design note (`reviews/phase-6-review/design-note.md`) identifies two bugs that need regression tests:

| Issue | Description | Test Required |
|-------|-------------|---------------|
| Hadamard 2x2 inverse normalization | `>>>1` shift missing in inverse mode for `h264_hadamard2x2` | Unit test comparing 2x2 forward+inverse round-trip |
| Inverse quantization DC position | Class override bug in DC coefficient handling | Requires quantizer module (not yet in repo) |

The 2x2 module exists only as an iverilog shim (`tb/unit/shims/h264_hadamard2x2.sv`) but has **no corresponding RTL source** in `rtl/src/`. This shim itself may contain the bug.

---

## 6. Infrastructure Testing Gaps

Beyond RTL verification, the project infrastructure scripts lack their own tests:

| Script | Test Coverage | Recommendation |
|--------|--------------|----------------|
| `scripts/run_sim.sh` | None | Add a self-test mode or CI smoke test that compiles a trivial module |
| `skills/rtl-lint-check/scripts/check_conventions.sh` | None | Add test cases with known-good and known-bad RTL files |
| `skills/rtl-synth-check/scripts/parse_yosys_stat.py` | None | Add unit tests with sample Yosys output |
| `skills/codec-rd-eval/scripts/bd_rate.py` | None | Add unit tests with known BD-rate values |
| `skills/codec-conformance-eval/scripts/compare_output.py` | None | Add unit tests with sample comparison data |
| `skills/codec-rd-eval/scripts/run_eval.py` | None | Add integration test |

---

## 7. Prioritized Recommendations

### P0 — Critical (blocks all verification)

1. **Create a C reference model** for `h264_hadamard4x4`
   - Location: `refc/src/hadamard4x4.c`
   - Required by CLAUDE.md absolute rule: "Do not write a Testbench without a Reference Model"
   - Simple implementation: ~50 lines of C for the butterfly + truncation/normalization

2. **Create Tier 1 smoke test** for `h264_hadamard4x4`
   - Location: `sim/h264_hadamard4x4/tb_h264_hadamard4x4_smoke.sv`
   - Validates reset, basic connectivity, single forward/inverse transactions
   - Use `scripts/run_sim.sh --sim iverilog` to verify it compiles and runs

3. **Create Tier 2 unit test** for `h264_hadamard4x4`
   - Location: `sim/h264_hadamard4x4/tb_h264_hadamard4x4.sv`
   - Compare RTL output vs reference model for deterministic test vectors
   - Cover forward/inverse modes, edge cases, pipeline stall/resume

### P1 — High (required for coverage closure)

4. **Create Tier 3 cocotb regression test**
   - Location: `sim/h264_hadamard4x4/test_h264_hadamard4x4.py`
   - Multi-seed random testing with Python reference
   - Backpressure randomization
   - Functional coverage points

5. **Add SVA formal properties**
   - Location: `sim/formal/h264_hadamard4x4_sva.sv`
   - Handshake protocol, pipeline invariants, liveness

6. **Run and capture lint results**
   - Run 3-tool lint (Verilator + Verible + slang)
   - Store in `lint/reports/`

7. **Run synthesis estimation**
   - Yosys synthesis for area/timing
   - Verify zero inferred latches
   - Store in `syn/reports/`

### P2 — Medium (infrastructure quality)

8. **Add the missing `h264_hadamard2x2.sv` RTL source** to `rtl/src/`
   - The iverilog shim exists but the original SystemVerilog source is missing
   - Investigate and fix the inverse normalization bug noted in the design note

9. **Create filelists** as required by project conventions
   - `rtl/filelist_h264_hadamard4x4.f` — module filelist
   - `rtl/filelist_top.f` — top-level filelist

10. **Add script-level tests** for infrastructure scripts
    - Self-test for `run_sim.sh` with a minimal module
    - Unit tests for `parse_yosys_stat.py` and `bd_rate.py`

### P3 — Low (nice to have)

11. **Create `DATA_WIDTH` parameterized test variants** (8-bit, 12-bit, 32-bit)
12. **Add waveform-based debug test** for the known 2x2 inverse normalization bug
13. **Generate coverage HTML reports** as CI artifacts
14. **Create Phase 4 Stream B artifacts** (SVA skeletons, CDC report, TB skeletons) as documentation

---

## 8. Coverage Estimation

Based on the current state (0 tests), estimated coverage metrics are:

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Line Coverage | 0% | >= 90% | 90%+ |
| Toggle Coverage | 0% | >= 80% | 80%+ |
| FSM Coverage | 0% | >= 70% | 70%+ |
| Functional Coverage | 0% | Full | 100% |
| Requirements Traced to Tests | 0/85 | 85/85 | 85 |

After implementing P0 + P1 recommendations, estimated coverage would be:

| Metric | After P0+P1 | Target | Status |
|--------|-------------|--------|--------|
| Line Coverage | ~85-95% | >= 90% | Likely MET |
| Toggle Coverage | ~75-85% | >= 80% | Likely MET |
| FSM Coverage | ~80-90% | >= 70% | MET |
| Functional Coverage | ~70% | Full | PARTIAL |

---

## 9. Verdict

**SIGNIFICANT GAPS** — The project has excellent verification infrastructure and well-defined processes, but zero actual tests exist for the RTL code in the repository. The P0 items (reference model + Tier 1/2 tests) should be addressed immediately to establish a functional verification baseline. The existing `run_sim.sh` script and cocotb templates make test creation straightforward once the reference model exists.
