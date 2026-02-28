---
name: rtl-sva-check
description: "This skill should be used when proving or disproving formal properties on RTL using SymbiYosys BMC and induction. Triggers on 'formal verification', 'prove property', 'SVA'."
---

<Purpose>
Extract SystemVerilog Assertions from RTL and run formal verification.
Outputs: sim/formal/*.sv assertion files + formal_verify.json with prove/fail status per property.

See `references/sva-patterns.md` for SVA temporal operator reference, common assertion patterns,
and SymbiYosys engine selection guide.
</Purpose>

<Use_When>
- RTL is lint-clean and protocol or safety properties need formal proof
- Exhaustive corner-case coverage is required (not achievable by simulation)
- A specific property needs to be proved or disproved
</Use_When>

<Do_Not_Use_When>
- Design is too large for formal (state explosion) — use rtl-func-verify with coverage instead
- Only simulation-based testing needed
</Do_Not_Use_When>

<Why_This_Exists>
Simulation cannot exhaustively cover all corner cases. Formal verification proves properties
hold for all possible inputs, catching bugs that would take millions of simulation cycles to find.
SymbiYosys is open-source and integrates cleanly with Yosys-based flows.
</Why_This_Exists>

<Coding_Convention_Requirements>
SVA property files MUST follow the project coding conventions (CLAUDE.md):
- Signal references: `i_` prefix for inputs, `o_` prefix for outputs (e.g., `i_valid`, `o_ready`)
- Clock references: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset references: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Use `logic` in helper code (NOT `reg`/`wire`)
- Assertion labels: descriptive snake_case (e.g., `no_fifo_overflow`, `valid_handshake`)
</Coding_Convention_Requirements>

<Execution_Policy>
- sva-extractor writes SVA properties targeting key protocol and safety requirements
- eda-runner runs SymbiYosys via Bash CLI for BMC and induction
- Results recorded in formal_verify.json per property
- Failed properties get counterexample analysis by waveform-analyzer
</Execution_Policy>

<Steps>
1. sva-extractor reads rtl/*/*.sv and uarch/*.md, writes sim/formal/*.sv with SVA properties
   - All signal names must match RTL port conventions (`i_`/`o_` prefixes, `sys_clk`, `sys_rst_n`)
   - Use temporal operators appropriately: `|->` (overlapping), `|=>` (non-overlapping), `##[M:N]` (delay range)
   - Guard `$past()` with a `past_valid` register to avoid undefined first-cycle behavior
   - See `references/sva-patterns.md` for handshake, FIFO, FSM, pipeline, and reset patterns
2. sva-extractor generates SymbiYosys .sby configuration file per module
   - Use `templates/sby-config.sby` as the configuration template
   - Use `templates/sva-property-template.sv` as the SVA property file scaffold
   - Engine selection: `smtbmc boolector` (default), `smtbmc yices` (bitvector-heavy), `abc pdr` (unbounded proof)
   - Generate both BMC (`mode bmc`) and prove (`mode prove`) configurations
   - Optionally generate cover (`mode cover`) to validate reachability
3. eda-runner runs BMC via Bash CLI: `sby -f sim/formal/{module}.sby`
4. eda-runner runs induction on BMC-passing properties (prove mode)
5. Parse results into formal_verify.json: {property, status: proved|failed|timeout, depth, engine}
6. For failed: waveform-analyzer extracts counterexample, attaches to formal_verify.json entry
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Write SVA properties for rtl/cabac_encoder/cabac_encoder.sv at sim/formal/cabac_encoder_props.sv. Use sys_clk/sys_rst_n, i_/o_ port prefixes per CLAUDE.md conventions. Cover: no overflow on o_data, valid handshake (i_valid/o_ready), FIFO no underflow.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run SymbiYosys formal verification via Bash CLI: sby -f sim/formal/cabac_encoder.sby. Parse output and write results to formal_verify.json with status per property.")

Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze SymbiYosys counterexample trace for failed property 'no_fifo_overflow'. Identify the input sequence that triggers the violation.")
```
</Tool_Usage>

<Examples>
<Good>
12 properties written using correct `i_`/`o_` signal names and `sys_clk`; 10 proved by induction;
1 BMC counterexample found at depth 7 (FIFO overflow when `i_valid` high and `o_ready` low for 8 cycles);
1 timeout (state space too large, flagged for simulation instead).
</Good>
<Bad>
Writing SVA properties so weak they are trivially true (e.g., assert(1)) — gives false confidence.
Using `clk` or `data_i` in SVA instead of `sys_clk` or `i_data` — signal name mismatch causes binding errors.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- SymbiYosys not installed → halt, instruct user to install (`pip install sbyosys` or from source)
- Property timeout (>200 depth) → mark as "timeout" in formal_verify.json, recommend simulation
- Counterexample found → report to user with waveform trace before any RTL fix
- SVA signal names do not match RTL ports → sva-extractor must fix before running formal
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] sim/formal/*.sv written with meaningful properties
- [ ] All SVA signal references match RTL port names (`i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`)
- [ ] formal_verify.json produced with status per property
- [ ] No "failed" status without counterexample attached
- [ ] Timeouts documented and flagged for simulation fallback
</Final_Checklist>

<Advanced>
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
</Advanced>
