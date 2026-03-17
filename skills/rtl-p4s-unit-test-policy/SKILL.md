---
name: rtl-p4s-unit-test-policy
description: "Policy rules, coding conventions, reference comparison modes, result schema, escalation rules, and checklists for Tier 2 unit testing. Pure reference — no orchestration."
user-invocable: false
---

# Tier 2 Unit Test Policy

## Coding Convention Requirements

Testbenches MUST follow project conventions:
- Port connections: `i_` prefix for inputs, `o_` prefix for outputs, `io_` for bidirectional
- Clock: `clk` (single domain) or `{domain}_clk` (multiple, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple, e.g., `sys_rst_n`) — NOT `rst_ni`
- Use `logic` only (NOT `reg`/`wire`)
- DUT instance: `u_` prefix (e.g., `u_dut`)
- Testbench filename: `tb_{module}.sv`

## Execution Policy

- testbench-dev writes SV testbenches per module (parallel), targeting uarch features
- Reference model comparison: Mode A (DPI-C) or Mode B (file compare) — auto-selected
- func-verifier runs simulations via run_sim.sh and reports results
- Failing tests trigger waveform analysis before reporting
- Gate: all unit tests pass AND reference comparison has zero mismatches

## Reference Comparison Modes

| Mode | Condition | Method |
|------|-----------|--------|
| A: DPI-C | `refc/build/lib{module}_ref.so` exists | SV TB calls ref functions via DPI-C, cycle-level comparison |
| B: File | DPI-C unavailable | RTL sim → output file, ref binary → output file, `diff` comparison |

**DPI-C setup**:
```bash
cd refc && mkdir -p build
gcc -std=c11 -shared -fPIC -o build/lib{module}_ref.so src/{module}_ref.c
```

## Result JSON Schema

```json
{
  "module": "{module}",
  "tier": 2,
  "ref_mode": "A_DPI" | "B_FILE",
  "features": [
    {"name": "fsm_idle_to_active", "status": "PASS", "req_ids": ["REQ-U-003"]},
    {"name": "pipeline_latency_3cyc", "status": "PASS", "req_ids": ["REQ-U-007"]},
    {"name": "valid_ready_handshake", "status": "PASS", "req_ids": ["REQ-U-012"]},
    {"name": "transform_accuracy", "status": "FAIL", "mismatch_cycle": 47, "req_ids": ["REQ-U-015"]}
  ],
  "ref_mismatches": 0,
  "pass_count": 5,
  "fail_count": 0,
  "total": 5,
  "gap_fill_round": {
    "executed": false,
    "before": {"line_pct": 52.1, "fsm_pct": 40.0},
    "after": {"line_pct": 67.3, "fsm_pct": 55.0}
  },
  "coverage": {
    "line_pct": 67.3,
    "fsm_pct": 55.0,
    "toggle_pct": 42.1
  },
  "func_coverage": {
    "covergroups_defined": 2,
    "bins_hit": 14,
    "bins_total": 20
  }
}
```

## Tier Transition Rules

- Tier 1 PASS (rtl-p4-implement Wave 4) → Tier 2 eligible
- Tier 2 PASS (this skill) → Tier 3 eligible (rtl-p5s-func-verify)
- Tier 2 FAIL → fix at rtl-p4s-bugfix, re-run Tier 2

## Escalation & Stop Conditions

- Module fails unit test and waveform analysis cannot identify root cause → escalate to rtl-architect
- Simulator not available → report to user, suggest installation or Docker EDA image
- Testbench uses wrong naming convention → testbench-dev must rewrite before simulation
- Reference model not available → escalate to user; build ref model first (Absolute Rule 2)
- Reference mismatches persist after RTL fix → escalate to ref-model-dev for model review

## Advanced

- Use `$dumpvars` for waveform capture even on passing tests (for coverage)
- Randomize input sequences with `$urandom` for broader coverage
- Use `always_ff`, `always_comb` in testbench helper modules (never `always @*`)

## Minimum Coverage Targets (Tier 2)

These are intentionally lower than P5 targets (90%/80%/70%) to keep Tier 2 fast while ensuring meaningful depth:

**Structural coverage:**
- FSM state coverage >= 50%
- Line coverage >= 60%

**Functional coverage (Tier 2):**

Gate-enforced (hard):
- At least one covergroup per module (`covergroups_defined >= 1` in results JSON)

Recommended guidance (not gate-enforced — P5 coverage-analyst verifies these):
- Each FSM should have a covergroup with explicit bins for all states defined in uarch spec
- Each valid/ready interface should have cross-coverage: {valid, ready} x {data = 0, mid, max}
- Bins should be derived from uarch feature list
- Functional coverage bins do NOT have a numeric threshold at Tier 2 — the goal is bin existence and hit, not closure (P5 handles closure)

**Traceability:**
- Each feature test tagged with REQ-U-* IDs from `docs/phase-3-uarch/iron-requirements.json`

## Final Checklist

- [ ] sim/{module}/tb_{module}.sv exists for every module
- [ ] All testbenches use `i_`/`o_` port prefixes, `sys_clk`/`sys_rst_n`, `u_dut`
- [ ] Each uarch feature has at least one test case with `req_ids` tracing
- [ ] valid/ready handshake protocol exercised (assert, deassert, backpressure) for modules with handshake interfaces
- [ ] Pipeline latency measured and matches uarch spec (docs/phase-3-uarch/{module}.md)
- [ ] Reference model comparison executed (DPI-C or file-based)
- [ ] Zero mismatches between RTL and reference model
- [ ] sim/{module}/{module}_unit_results.json produced with per-feature status + coverage summary
- [ ] FSM state coverage >= 50%, line coverage >= 60%
- [ ] Coverage gap fill round executed if initial coverage below thresholds
- [ ] All simulations compile and complete without crashes
- [ ] All unit tests pass
- [ ] Failure analysis done for any initial failures
- [ ] run_sim.sh used (not direct iverilog/verilator invocation)
