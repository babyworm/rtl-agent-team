---
name: rtl-p5s-cdc-policy
description: "Internal reference: rtl p5s cdc policy (agent-loaded; do not invoke)."
user-invocable: false
---

# CDC Verification Policy

## CDC Coding Conventions

CDC analysis MUST recognize the project clock/reset naming conventions (CLAUDE.md):
- Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`, `axi_clk`, `pixel_clk`)
  - NOT `clk_i`, `clk_sys` — these are non-conformant
- Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`, `axi_rst_n`)
  - NOT `rst_ni` — this is non-conformant
- Clock/reset ports: `i_` prefix not required (exception). All other ports require `i_`/`o_`/`io_`
- Synchronizer instances: `u_` prefix (e.g., `u_sync_axi_to_sys`)
- Gray code modules: `u_` prefix (e.g., `u_gray_encoder`)

If RTL uses non-conformant clock/reset names, flag as a CONVENTION VIOLATION in the report
in addition to any CDC violations.

## Escalation & Stop Conditions

- VIOLATION found → surface immediately, do NOT auto-insert synchronizers
- CONVENTION violation found → report alongside CDC violations, recommend fix before sign-off
- Clock domains cannot be determined from RTL alone → ask user for clocking architecture doc
- Tool (vc_cdc, Meridian, or spyglass) not available → use structural RTL analysis only

## Final Checklist

- [ ] All clock domains identified in RTL (expect `{domain}_clk` format)
- [ ] All cross-domain paths analyzed
- [ ] Non-conformant clock/reset names flagged as CONVENTION violations
- [ ] lint/cdc/cdc_report.md written with VIOLATION/CAUTION/CONVENTION/INFO classification
- [ ] syn/constraints/cdc_constraints.sdc written with correct clock domain names
- [ ] CDC replay script exists (lint/cdc/replay/run_cdc_*_latest.sh)
- [ ] RTL not modified
- [ ] Violation count reported to user

## Synchronizer Type Selection Guide

| Crossing Type | Recommended Synchronizer |
|---------------|-------------------------|
| Single-bit control | 2-FF synchronizer (3-FF for high-freq) |
| Multi-bit counter | Gray code FIFO |
| Multi-bit data bus | Handshake (REQ/ACK) or MUX synchronizer |
| Single-cycle pulse | Pulse synchronizer (toggle-based) |
| Bulk data (cross-domain R+W) | Dual-port SRAM (`sram_dp` with `wclk`/`rclk`) |
| Reset signal | Async assert, sync deassert reset synchronizer |

### Dual-Port SRAM as CDC Boundary

`sram_dp` from `rtl/common/` is inherently a CDC element — write port on `wclk`, read port on `rclk`.
- `wclk` and `rclk` MUST be in different clock domains (verified in CDC analysis)
- No additional synchronizer needed on the data path (SRAM handles internally)
- Address/control signals (`i_waddr`, `i_wen`, `i_raddr`, `i_ren`) must be generated within their respective clock domains
- SDC: `set_clock_groups -asynchronous` between `wclk` and `rclk` domains
- If used as async FIFO backend: verify gray-coded pointers cross correctly (separate 2-FF sync on pointers)
- CDC checker should recognize `sram_dp` instances and verify wclk/rclk domain assignment

For comprehensive CDC analysis, commercial tools (SpyGlass CDC, Conformal CDC, Questa CDC)
provide formal proof of synchronizer correctness beyond structural analysis.

See `references/cdc-patterns.md` for SDC constraint templates, violation checklist,
and detailed synchronizer implementation guidance.
