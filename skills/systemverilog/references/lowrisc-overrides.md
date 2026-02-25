# lowRISC Style Guide — Project Overrides

This document lists all deviations from the lowRISC SystemVerilog Coding Style Guide.
Base: https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md

## Override Summary

| # | lowRISC Default | Project Override | Reason |
|---|----------------|-----------------|--------|
| 1 | Port suffix: `_i`, `_o`, `_io` | Port prefix: `i_`, `o_`, `io_` | Prefix makes direction visible at signal usage site, not just declaration |
| 2 | Clock: `clk_i` | Clock: `{domain}_clk` | Multi-clock designs need domain identification |
| 3 | Reset: `rst_ni` (active-low) | Reset: `{domain}_rst_n` (active-low) | Consistent with clock domain naming |

## Detailed Rationale

### Override 1: Port Direction Prefix

**lowRISC**: `data_i`, `valid_o`, `sda_io`
**Project**: `i_data`, `o_valid`, `io_sda`

**Why prefix is preferred:**
- When reading `i_data` in logic, direction is immediately visible
- With suffix (`data_i`), the signal name body (`data`) comes first — direction is an afterthought
- Prefix groups signals by direction when sorted alphabetically
- Common in industry ASIC flows (ARM, Synopsys reference designs)

### Override 2: Clock Domain Naming

**lowRISC**: Single `clk_i` input
**Project**: `{domain}_clk` — e.g., `sys_clk`, `pixel_clk`, `axi_clk`

**Why domain-prefixed clocks:**
- Real designs often have multiple clock domains
- Domain name in clock signal prevents accidental cross-domain connections
- CDC analysis tools can auto-identify domains from naming pattern
- Single-domain designs use `sys_clk` as the default domain

### Override 3: Reset Domain Naming

**lowRISC**: `rst_ni` (active-low, suffix)
**Project**: `{domain}_rst_n` — e.g., `sys_rst_n`, `pixel_rst_n`

**Why domain-prefixed resets:**
- Matches clock domain naming for consistency
- Each clock domain should have its own reset
- `_n` suffix clearly indicates active-low (widely understood)

## What Stays the Same

All other lowRISC rules remain in effect:
- `logic` only (no `reg`/`wire`)
- `always_ff` / `always_comb` (no `always`)
- `typedef enum` / `typedef struct packed`
- ANSI port style
- One module per file
- Package-based type sharing
- `unique case` / `priority case`
