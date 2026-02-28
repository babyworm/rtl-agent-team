---
name: rtl-protocol-verify
description: "This skill should be used when verifying bus protocol compliance (AXI/AHB/APB) using SVA handshake and ordering rules."
---

<Purpose>
Verify that RTL bus interfaces comply with AXI, AHB, or APB protocol specifications
using formal SVA assertions and simulation-based protocol checking.
Outputs: reviews/phase-5-verify/protocol-report.md + sim/formal/{bus}_assertions.sv.
</Purpose>

<Use_When>
- RTL module has AXI, AHB, or APB interface
- Protocol compliance needed before SoC integration
- Checking a specific protocol violation reported in simulation
- Adding protocol assertions to an existing design
</Use_When>

<Do_Not_Use_When>
- Custom/proprietary protocol (use rtl-sva-check for general SVA)
- Only functional behavior matters, not protocol compliance
- Protocol is already verified and RTL has not changed
</Do_Not_Use_When>

<Why_This_Exists>
Protocol violations cause SoC-level integration failures that are hard to debug.
Formal SVA assertions catch violations exhaustively; simulation-based checking
catches violations on real traffic patterns. Both are needed for confidence.
</Why_This_Exists>

<Coding_Convention_Requirements>
Protocol SVA assertions MUST use the project port naming conventions (CLAUDE.md):

AXI signal naming (with `i_`/`o_` prefix based on slave perspective):
- Write Address: `i_awvalid`, `o_awready`, `i_awaddr`, `i_awlen`, `i_awsize`, `i_awburst`
- Write Data: `i_wvalid`, `o_wready`, `i_wdata`, `i_wstrb`, `i_wlast`
- Write Response: `o_bvalid`, `i_bready`, `o_bresp`
- Read Address: `i_arvalid`, `o_arready`, `i_araddr`, `i_arlen`, `i_arsize`, `i_arburst`
- Read Data: `o_rvalid`, `i_rready`, `o_rdata`, `o_rresp`, `o_rlast`

AHB signal naming (slave perspective):
- `i_hsel`, `i_haddr`, `i_htrans`, `i_hwrite`, `i_hsize`, `i_hburst`
- `i_hwdata`, `o_hrdata`, `o_hready`, `o_hresp`

APB signal naming (slave perspective):
- `i_psel`, `i_penable`, `i_pwrite`, `i_paddr`, `i_pwdata`
- `o_prdata`, `o_pready`, `o_pslverr`

Clock/Reset: `{domain}_clk` (e.g., `axi_clk` or `sys_clk`), `{domain}_rst_n`
NOT: `ACLK`, `ARESETn`, `clk_i`, `rst_ni`

Note: For master-perspective modules, `i_`/`o_` directions are reversed.
</Coding_Convention_Requirements>

<Execution_Policy>
- sva-extractor identifies bus interface and extracts existing assertions
- protocol-checker writes protocol-specific SVA assertions per spec using `i_`/`o_` signal names
- eda-runner binds assertions and runs simulation via Bash CLI
- Report: assertions bound, violations found, waveform evidence
</Execution_Policy>

<Steps>
1. sva-extractor reads RTL to identify bus type (AXI/AHB/APB) and interface signals
   - Verifies signals use `i_`/`o_` prefix convention
   - Flags any non-conformant signal names (e.g., `AWVALID` instead of `i_awvalid`)
2. protocol-checker writes sim/formal/{bus}_assertions.sv using `i_`/`o_` signal names:
   - See `examples/axi4-lite-assertions.sv` for complete AXI4-Lite assertion set
   - See `examples/apb-assertions.sv` for APB3 protocol assertion patterns
   - Handshake rules: `i_awvalid`/`o_awready` stability, `i_wvalid`/`o_wready` timing
   - Ordering rules (AXI write data before response, etc.)
   - Signal stability rules (stable during wait states)
   - Clock: `@(posedge sys_clk) disable iff (!sys_rst_n)` (or appropriate domain clock)
3. eda-runner binds assertions and runs cocotb regression via Bash CLI
4. Capture assertion violations with cycle number and waveform region
5. Write reviews/phase-5-verify/protocol-report.md (use `templates/protocol-report.md` as format template): violations, assertion coverage, PASS/FAIL
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Read rtl/axi_slave/axi_slave.sv. Identify AXI4 interface signals with i_/o_ prefix convention (i_awvalid, o_awready, etc.). Verify all signal names follow CLAUDE.md conventions. List all existing SVA assertions if any.")

Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="Write complete AXI4 protocol SVA assertions for axi_slave.sv interface using i_/o_ signal names per CLAUDE.md. Use sys_clk/sys_rst_n (or axi_clk/axi_rst_n). Cover: i_awvalid/o_awready handshake stability, i_wvalid/o_wready ordering, no X/Z on valid channels. Save to sim/formal/axi4_assertions.sv.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Bind sim/formal/axi4_assertions.sv to rtl/axi_slave/axi_slave.sv. Run cocotb regression via Bash CLI with assertions enabled: make -C sim/axi_slave SIM=icarus TOPLEVEL=axi_slave MODULE=test_axi_slave. Report all assertion violations with cycle numbers.")
```
</Tool_Usage>

<Examples>
<Good>
sva-extractor identifies AXI4 slave interface with `i_awvalid`, `o_awready`, `i_wdata`, etc.;
protocol-checker writes 15 assertions using `sys_clk` and `i_`/`o_` signal names covering
all AXI4-Lite rules; eda-runner finds 1 violation: `i_wdata` unstable during `i_wvalid` high
and `o_wready` low; cycle 340 waveform captured; report written.
</Good>
<Bad>
Only checking VALID/READY handshake and ignoring ordering rules — misses the class of
AXI ordering violations that cause data corruption in multi-outstanding-transaction scenarios.
Using `AWVALID`, `WDATA`, `ACLK` in SVA — violates project conventions and causes signal binding errors.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Protocol type cannot be identified from RTL → ask user to specify (AXI3/AXI4/AXI4-Lite/AHB-Lite/APB3)
- Protocol violation found → report with waveform evidence, do NOT auto-fix RTL
- Assertions cause simulation performance >10x slowdown → report to user, suggest formal tool
- RTL uses non-conformant signal names (e.g., `AWVALID`) → flag as convention violation, request fix before protocol verification
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Bus protocol type identified
- [ ] All protocol signals use `i_`/`o_` prefix convention
- [ ] SVA assertions use correct signal names (`i_awvalid`, `o_awready`, `sys_clk`, etc.)
- [ ] SVA assertions written covering all mandatory protocol rules
- [ ] Assertions bound and simulation run via Bash CLI
- [ ] reviews/phase-5-verify/protocol-report.md written with PASS/FAIL
- [ ] Violations reported with cycle numbers
- [ ] RTL not modified
</Final_Checklist>

<Advanced>
For AXI4 full (not Lite), also check: burst length/size consistency, wrap alignment, exclusive access.
For multi-clock designs, use `axi_clk`/`axi_rst_n` in assertion clock instead of `sys_clk`.
Protocol assertions can also be run with SymbiYosys formal (via rtl-sva-check skill) for exhaustive coverage.

Key AXI protocol rules to verify:
1. **VALID must not depend on READY** — xVALID must assert independently
2. **VALID must hold until handshake** — cannot drop VALID before READY
3. **Data/control stable while waiting** — no changes while VALID && !READY
4. **Write response after last data** — BVALID only after WLAST accepted
5. **Read data ordering** — RDATA returned in address request order (per ID)

See `references/axi-protocol-rules.md` for complete SVA assertion templates per channel,
ordering rules, AXI4 vs AXI4-Lite differences, and common violations found in practice.
</Advanced>
