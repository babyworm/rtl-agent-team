---
name: rtl-p5s-integration-test-policy
description: "Policy rules, coding conventions, test ordering, result schema, escalation rules, and checklists for Tier 4 integration testing. Pure reference — no orchestration."
user-invocable: false
---

# Tier 4 Integration Test Policy

## Coding Convention Requirements

Integration testbenches MUST follow project conventions:
- Port connections: `i_` prefix for inputs, `o_` prefix for outputs
- Clock: `clk` (single domain) or `{domain}_clk` (multiple, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple, e.g., `sys_rst_n`) — NOT `rst_ni`
- DUT instance: `u_dut` for top-level, `u_` prefix for sub-modules
- Use `logic` only (NOT `reg`/`wire`)
- cocotb signals: `dut.sys_clk`, `dut.i_*`, `dut.o_*`

## Integration Test Ordering (mandatory sequence)

1. Static connectivity checks first (fast, catches wiring bugs)
2. Simple data flow (single transaction end-to-end)
3. Sustained throughput (back-to-back transactions)
4. Backpressure and stall scenarios
5. Error injection and recovery

## Result JSON Schema

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

## Simulation Commands

**SV TB**:
```bash
scripts/run_sim.sh --sim verilator --top tb_{top}_integration \
  --filelist rtl/filelist_top.f --outdir sim/top --trace \
  sim/top/tb_{top}_integration.sv
```

**cocotb**:
```bash
make -C sim/top SIM=verilator TOPLEVEL={top} MODULE=test_{top}_integration
```

**Fallback (iverilog)**:
```bash
scripts/run_sim.sh --sim iverilog --top tb_{top}_integration \
  --filelist rtl/filelist_top.f --outdir sim/top --trace \
  sim/top/tb_{top}_integration.sv
```

## Multi-Clock Domain Integration

- Verify CDC synchronizers are connected correctly
- Test data transfer across clock domains
- Use rtl-p5s-cdc-verify for detailed CDC analysis

## Tier Transition Rules

- Tier 3 PASS (rtl-p5s-func-verify) → Tier 4 eligible
- Tier 4 PASS (this skill) → Phase 5 final compliance eligible
- Tier 4 FAIL → isolate to module, fix via rtl-p4s-bugfix, retest Tier 2→3→4

## Escalation & Stop Conditions

- Connectivity check fails (width mismatch, missing connection) → rtl-coder must fix before sim
- End-to-end reference mismatch → waveform-analyzer + func-verifier isolate to module → Tier 2 retest
- Handshake protocol violation → protocol-checker for detailed analysis
- Cross-module timing issue → timing-advisor for pipeline analysis
- More than 3 integration bugs found → escalate to rtl-architect for interface review

## Final Checklist

- [ ] Connectivity check passed (reset propagation, clock, port widths)
- [ ] Integration TB written (SV or cocotb)
- [ ] End-to-end data flow tests executed
- [ ] Handshake/backpressure tests executed
- [ ] End-to-end reference comparison done (byte-by-byte)
- [ ] sim/top/integration_results.json produced
- [ ] All integration tests PASS
- [ ] run_sim.sh used for SV TB simulation
- [ ] Waveform analysis done for any failures
