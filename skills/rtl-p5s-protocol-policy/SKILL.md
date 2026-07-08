---
name: rtl-p5s-protocol-policy
description: "Internal reference: rtl p5s protocol policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Protocol Verification Policy

## Protocol Signal Naming Conventions

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

## Escalation & Stop Conditions

- Protocol type cannot be identified from RTL → ask user to specify (AXI3/AXI4/AXI4-Lite/AHB-Lite/APB3)
- Protocol violation found → report with waveform evidence, do NOT auto-fix RTL
- Assertions cause simulation performance >10x slowdown → report to user, suggest formal tool
- RTL uses non-conformant signal names (e.g., `AWVALID`) → flag as convention violation, request fix before protocol verification

## Final Checklist

- [ ] Bus protocol type identified
- [ ] All protocol signals use `i_`/`o_` prefix convention
- [ ] SVA assertions use correct signal names (`i_awvalid`, `o_awready`, `sys_clk`, etc.)
- [ ] SVA assertions written covering all mandatory protocol rules
- [ ] Assertions bound and simulation run via Bash CLI
- [ ] reviews/phase-5-verify/protocol-report.md written with PASS/FAIL
- [ ] Violations reported with cycle numbers
- [ ] RTL not modified

## AXI4 Full Rules and Key Protocol Rules

For AXI4 full (not Lite), also check: burst length/size consistency, wrap alignment, exclusive access.
For multi-clock designs, use `axi_clk`/`axi_rst_n` in assertion clock instead of `sys_clk`.
Protocol assertions can also be run with SymbiYosys formal (via rtl-p5s-sva-check skill) for exhaustive coverage.

Key AXI protocol rules to verify:
1. **VALID must not depend on READY** — xVALID must assert independently
2. **VALID must hold until handshake** — cannot drop VALID before READY
3. **Data/control stable while waiting** — no changes while VALID && !READY
4. **Write response after last data** — BVALID only after WLAST accepted
5. **Read data ordering** — RDATA returned in address request order (per ID)

See `references/axi-protocol-rules.md` for complete SVA assertion templates per channel,
ordering rules, AXI4 vs AXI4-Lite differences, and common violations found in practice.
