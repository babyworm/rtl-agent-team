# RTL Bug Reproduction Conventions

A quick reference for `rtl-bug-repro`. Stays under 150 lines so it can be consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Bug directory | `sim/bugs/{bug_id}/` | `sim/bugs/BUG-042/` |
| Reproduction testbench | `repro_tb.sv` inside bug dir | `sim/bugs/BUG-042/repro_tb.sv` |
| Root cause document | `root_cause.md` inside bug dir | `sim/bugs/BUG-042/root_cause.md` |
| Waveform dump | `repro_tb.vcd` or `repro_tb.fst` | `sim/bugs/BUG-042/repro_tb.vcd` |
| Port prefix | `i_` input, `o_` output, `io_` inout | `i_data`, `o_valid` |
| Clock port | `clk` (single) or `{domain}_clk` | `sys_clk`, `pixel_clk` |
| Reset port | `rst_n` (single) or `{domain}_rst_n` (active-low async) | `sys_rst_n` |
| DUT instance | `u_dut` | `u_dut` |
| Signal types | `logic` only — no `reg`/`wire` in SV TBs | |

The bug_id must match the reported identifier exactly (preserving case, e.g., `BUG-042` not `bug042`).

## 2. Output schema

### repro_tb.sv structure

```
module repro_tb;
  // 1. Clock/reset generation
  // 2. DUT instantiation (u_dut, all ports connected)
  // 3. Minimal stimulus sequence (reproduce failure only)
  // 4. Assertion / $display at failure point
  // 5. $finish after pass or timeout
endmodule
```

Minimal means: fewest input transitions needed to trigger the first divergence cycle.
Do not include reset sequences, corner cases, or alternate paths unrelated to the bug.

### root_cause.md structure

```markdown
# Bug {bug_id} — Root Cause Analysis

## Symptom
{One sentence: what the failing test reported.}

## First Failure Cycle
Cycle {N}: signal `{hierarchical.path}` expected `{expected}`, got `{actual}`.

## Signal Trace
{Table or list of signal values at relevant cycles leading to divergence.}

## Suspected Root Cause
{RTL file}, line {N}: {hypothesis about the bug.}

## Clock / Reset Context
Clock domain: `{domain}_clk`. Reset: `{domain}_rst_n` (active-low async).

## Reproduction Confirmed
repro_tb.sv reproduces failure at cycle {N}. Run:
`scripts/run_sim.sh --sim iverilog --top repro_tb --outdir sim/bugs/{bug_id} --trace ...`
```

## 3. Length guidance

- **root_cause.md**: 30–80 lines. Signal trace table should cover only cycles surrounding
  the divergence — not the full simulation. Suspected Root Cause section: 2–5 lines.
- **repro_tb.sv**: Target 30–80 lines. If the TB exceeds 100 lines, consider whether
  the stimulus is truly minimal — trim until the failure no longer reproduces, then add
  back the last removed stimulus.
- Per-signal description in the trace: 1 line. State the actual vs expected value only.

## 4. Anti-patterns

- Do not fix RTL in the same session — reproduce and document only. Fixes are a separate step.
- Do not fabricate waveform values if the VCD file is unreadable — report the parse failure.
- Do not include synthesis attributes or timing constraints in repro_tb.sv.
- Do not use `reg`/`wire` types in SystemVerilog testbenches — use `logic`.
- Do not guess the root cause without a confirmed-reproducing TB — label hypotheses as
  "suspected" until a minimal TB confirms the failure path.
- Do not leave `root_cause.md` with "TODO" sections. If the root cause cannot be determined,
  document the limit of analysis and escalate per `<Escalation_And_Stop_Conditions>`.
