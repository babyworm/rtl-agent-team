# Simulation & Verification

## 4-Tier Testing Hierarchy

| Tier | Name | Skill | Scope | Prerequisite |
|------|------|-------|-------|-------------|
| 1 | Smoke Test | `rtl-p4-implement` Wave 4 | Connectivity, R/W, basic ops | Lint pass |
| 2 | Unit Test | `rtl-p4s-unit-test` | Ref model comparison, uarch features | Tier 1 pass |
| 3 | Module Regression | `rtl-p5s-func-verify` | cocotb multi-seed, coverage closure | Tier 2 pass |
| 4 | Integration | `rtl-p5s-integration-test` | Cross-module data flow, end-to-end | Tier 3 pass or PARTIAL_PASS |

**Progression rules:**
- Each tier must PASS (or PARTIAL_PASS for Tier 3→4) before proceeding to the next
- On FAIL: fix via `rtl-p4s-bugfix`, re-verify at the failing tier
- Tier 3 provides multi-seed regression via `rtl-p5s-func-verify`
- Coverage targets (Tier 3): line >= 90%, toggle >= 80%, FSM >= 70%
- **SVA/Coverpoint 3+ iteration rule**: Min 3 rounds of refinement (Draft → Strengthen → Harden)

## TB File Naming

```
sim/{module}/
├── tb_{module}_smoke.sv     # Tier 1: smoke test
├── tb_{module}.sv           # Tier 2: unit test (SV)
├── test_{module}.py         # Tier 3: cocotb regression
└── Makefile                 # cocotb Makefile
sim/top/                     # Tier 4: integration tests
├── tb_top_integration.sv
└── test_top_integration.py
```

## Simulator Selection

| Simulator | When to Use | Strengths |
|-----------|-------------|-----------|
| **verilator** (default) | All simulation unless fallback needed | Fast (compiled), lint, coverage |
| **iverilog** (fallback) | 4-state X/Z sim, delay-based, verilator-unsupported SV | Full 4-state, delay modeling |

## Execution Commands

```bash
# SV testbench (simulator-agnostic)
scripts/run_sim.sh --sim verilator --top tb_module --outdir sim/{module} --trace files...
scripts/run_sim.sh --help  # Full options

# cocotb
make -C sim/{module} SIM=verilator TOPLEVEL={module}_top MODULE=test_{module}
# Fallback: SIM=icarus

# Waveform viewer
gtkwave sim/{module}/dump.vcd
```

## Phase 4 Parallel Streams

```
Stream A: RTL coding (wave-based) → lint → unit TB (sim/{module}/) → unit sim
Stream B: SVA skeletons + CDC topology + TB skeletons (from uarch, parallel with A)
Merge: Phase 4→5 Gate (Stream A PASS + Stream B artifacts ready)
```

## Other Directories

- `formal/` — SVA formal verification (.sby configs)
- `lint/cdc/` — CDC analysis reports
- `sim/uvm/` — UVM testbenches (commercial sim required)
- `sim/bugs/{bug_id}/` — Bug reproduction TBs + root_cause.md
- `sim/regression/` — Multi-seed regression outputs
- `sim/coverage/` — Coverage reports (merged.info, html/)
- `sim/conformance/` — Conformance test outputs (RTL vs golden)
- `sim/consistency/` — 3-way model consistency check outputs

<!-- rat-version: 0.7.7 -->
