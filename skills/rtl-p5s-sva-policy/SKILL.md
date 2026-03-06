---
name: rtl-p5s-sva-policy
description: "Policy rules, SVA coding conventions, SymbiYosys engine guide, 3-round iterative refinement protocol, and formal verification checklists. Pure reference — no orchestration."
user-invocable: false
---

# SVA / Formal Verification Policy

## SVA Coding Conventions

SVA property files MUST follow the project coding conventions (CLAUDE.md):
- Signal references: `i_` prefix for inputs, `o_` prefix for outputs (e.g., `i_valid`, `o_ready`)
- Clock references: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset references: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Use `logic` in helper code (NOT `reg`/`wire`)
- Assertion labels: descriptive snake_case (e.g., `no_fifo_overflow`, `valid_handshake`)

## SVA Property Iterative Refinement (minimum 3 rounds)

SVA property extraction must iterate at least 3 times to strengthen assertion quality.
Each round builds upon the previous:

- **Round 1 (Draft)**: Extract initial properties from RTL and uarch spec. Focus on safety (no overflow, no deadlock) and protocol (handshake) properties.
- **Round 2 (Strengthen)**: Review Round 1 properties for completeness. Add missing edge cases: reset behavior, boundary conditions, back-to-back transactions, error paths. Add `cover` properties to verify reachability. Check for vacuous assertions.
- **Round 3 (Harden)**: Cross-check against spec requirements. Add liveness properties (`##[1:N]` bounded eventually). Verify assume/assert balance (not over-constrained). Add cross-module interface properties if applicable.
- **Additional rounds**: Continue if coverage of spec requirements < 100% or if new RTL paths are discovered.

Each round produces a review note at `.rtl-agent-team/scratch/phase-5/sva-iteration-r{N}.md`.

## Escalation & Stop Conditions

- SymbiYosys not installed → halt, instruct user to install (`pip install sbyosys` or from source)
- Property timeout (>200 depth) → mark as "timeout" in formal_verify.json, recommend simulation
- Counterexample found → report to user with waveform trace before any RTL fix
- SVA signal names do not match RTL ports → sva-extractor must fix before running formal

## Final Checklist

- [ ] sim/formal/*.sv written with meaningful properties
- [ ] All SVA signal references match RTL port names (`i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`)
- [ ] formal_verify.json produced with status per property
- [ ] No "failed" status without counterexample attached
- [ ] Timeouts documented and flagged for simulation fallback

## Assume/Assert Principle and Engine Guide

Use assume statements to constrain inputs to legal protocol ranges before proving.
**Principle: assume inputs, assert outputs.** Inputs are constrained with `assume`; outputs are verified with `assert`.
Target properties: no deadlock, no overflow, interface protocol compliance, data integrity.
Assertion clock: `@(posedge sys_clk) disable iff (!sys_rst_n)` for synchronous properties.

See `examples/handshake-assertions.sv` for valid/ready handshake SVA patterns.
See `examples/fifo-assertions.sv` for FIFO overflow/underflow assertion patterns.

SymbiYosys engine guide:
| Engine | Mode | Best For |
|--------|------|----------|
| `smtbmc boolector` | BMC, prove | General purpose (default) |
| `smtbmc yices` | BMC, prove | Bitvector-heavy, often fastest |
| `smtbmc z3` | BMC, prove | Arithmetic-heavy designs |
| `abc pdr` | prove only | Unbounded proof via PDR |

See `references/sva-patterns.md` for complete temporal operator reference and pattern library.

**sv2v conversion note:**
SymbiYosys relies on Yosys for reading design files. Yosys has limited SystemVerilog support,
so all RTL `.sv` files must be converted to Verilog via `sv2v` before running `sby`.
SVA property files (sim/formal/*_props.sv) are read with `-formal -sv` and do NOT need conversion.
```bash
# Convert before every sby run:
sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v
sby -f sim/formal/{module}.sby   # .sby references _v2v.v, not .sv
```
