---
name: rtl-p5s-sva-policy
description: "Internal reference: rtl p5s sva policy (agent-loaded; do not invoke)."
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

## SVA Properties — one pass

Write the properties once. Cover safety (no overflow, no deadlock), protocol handshakes, reset and boundary behavior, `cover` for reachability, and bounded liveness (`##[1:N]`). Keep assume on inputs and assert on outputs. Name requirements you could not express. Do not schedule a second extraction.

Save the note at `.rat/scratch/phase-5/sva-iteration-{module}.md`.

## Escalation & Stop Conditions

- SymbiYosys not installed → halt and run `/rtl-agent-team:rat-setup`; use the official OSS CAD Suite or source installation guide (https://yosyshq.readthedocs.io/projects/sby/en/latest/install.html)
- Property timeout (>200 depth) → mark as "timeout" in formal_verify.json, recommend simulation
- Counterexample found → report to user with waveform trace before any RTL fix
- SVA signal names do not match RTL ports → sva-extractor must fix before running formal

## Final Checklist

- [ ] `formal/*_props.sv` written with meaningful concurrent SVA properties for commercial formal tools
- [ ] `formal/*_formal_harness.sv` written with Yosys-compatible procedural immediate checks for OSS SBY
- [ ] All SVA signal references match RTL port names (`i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`)
- [ ] `formal/formal_verify_{module}.json` produced with task-level result status
- [ ] No "failed" status without counterexample attached
- [ ] Timeouts documented and flagged for simulation fallback

## Assume/Assert Principle and Engine Guide

Use assume statements to constrain inputs to legal protocol ranges before proving.
**Principle: assume inputs, assert outputs.** Inputs are constrained with `assume`; outputs are verified with `assert`.
Target properties: no deadlock, no overflow, interface protocol compliance, data integrity.
Assertion clock: `@(posedge sys_clk) disable iff (!sys_rst_n)` for synchronous properties.

See `{plugin_root}/skills/rtl-p5s-sva-check/examples/handshake-assertions.sv` for valid/ready handshake SVA patterns.
See `{plugin_root}/skills/rtl-p5s-sva-check/examples/fifo-assertions.sv` for FIFO overflow/underflow assertion patterns.

SymbiYosys engine guide:
| Engine | Mode | Best For |
|--------|------|----------|
| `smtbmc boolector` | BMC, prove | General purpose (default) |
| `smtbmc yices` | BMC, prove | Bitvector-heavy, often fastest |
| `smtbmc z3` | BMC, prove | Arithmetic-heavy designs |
| `abc pdr` | prove only | Unbounded proof via PDR |

See `{plugin_root}/skills/rtl-p5s-sva-check/references/sva-patterns.md` for complete temporal operator reference and pattern library.

**sv2v conversion note:**
SymbiYosys relies on Yosys for reading design files. Yosys has limited SystemVerilog
support, so DUT RTL `.sv` files need explicit Verilog conversion before `sby`.
Run sv2v on DUT RTL only:
```bash
sv2v --write=formal/{module}_v2v.v rtl/{module}/*.sv
test -s formal/{module}_v2v.v
sby -f formal/{module}.sby bmc
sby -f formal/{module}.sby prove
sby -f formal/{module}.sby cover
```
Do NOT run sv2v on full concurrent SVA property files (`formal/*_props.sv`);
sv2v can remove assertions/covers. For OSS SBY, generate a dedicated
`formal/*_formal_harness.sv` from `yosys-formal-harness-template.sv` and use
procedural immediate `assert(...)`, `assume(...)`, and `cover(...)` in that harness.
Keep concurrent SVA assets as commercial-formal input.
