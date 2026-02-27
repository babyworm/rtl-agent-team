# lowRISC Style Guide — Project Overrides

This document lists all deviations from the lowRISC SystemVerilog Coding Style Guide.
Base: https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md

## Override Summary

| # | lowRISC Default | Project Override | Reason |
|---|----------------|-----------------|--------|
| 1 | Port suffix: `_i`, `_o`, `_io` | Port prefix: `i_`, `o_`, `io_` (mandatory) | Prefix makes direction visible at signal usage site |
| 2 | Clock: `clk_i` | Clock: `clk` (single) or `{domain}_clk` (multi) | Multi-clock designs need domain identification |
| 3 | Reset: `rst_ni` (active-low) | Reset: `rst_n` (single) or `{domain}_rst_n` (multi) | Consistent with clock domain naming |
| 4 | Parameter: `UpperCamelCase` | Parameter: `ALL_CAPS` | CamelCase completely prohibited |
| 5 | Enum value: `UpperCamelCase` (`StIdle`) | Enum value: `ALL_CAPS` (`ST_IDLE`) | CamelCase completely prohibited |
| 6 | localparam: `UpperCamelCase` or `ALL_CAPS` | localparam: `L_` prefix + `ALL_CAPS` | Distinguish external/internal parameters |

## Detailed Rationale

### Override 1: Port Direction Prefix (Mandatory, clk/rst Excepted)

**lowRISC**: `data_i`, `valid_o`, `sda_io` (suffix)
**Project**: `i_data`, `o_valid`, `io_sda` (prefix, mandatory)

**Clock/Reset Exception**: `clk`, `sys_clk`, `rst_n`, `sys_rst_n` are used without the `i_` prefix.
Clock and reset are always inputs, so the direction prefix is unnecessary. They are also the most
frequently referenced signals throughout the RTL, so brevity is prioritized.

**Why prefix is mandatory (for other signals):**
- When reading `i_data` in logic, direction is immediately visible
- With suffix (`data_i`), the signal name body (`data`) comes first — direction is an afterthought
- Prefix groups signals by direction when sorted alphabetically
- Common in industry ASIC flows (ARM, Synopsys reference designs)

### Override 2: Clock Naming

**lowRISC**: Single `clk_i` input
**Project**: `clk` (single domain) or `{domain}_clk` (multi-domain) — e.g., `sys_clk`, `pixel_clk`

**Why:**
- Single clock designs use the concise `clk`
- Multi-clock designs use domain prefix to prevent cross-domain mistakes
- CDC analysis tools auto-identify domains from naming patterns

### Override 3: Reset Naming

**lowRISC**: `rst_ni` (active-low, suffix)
**Project**: `rst_n` (single domain) or `{domain}_rst_n` (multi-domain)

**Why:**
- Consistent with clock naming convention
- `_n` suffix clearly indicates active-low

### Override 4: CamelCase Completely Prohibited

**lowRISC**: Parameter `UpperCamelCase` (`DataWidth`), Enum value `UpperCamelCase` (`StIdle`)
**Project**: Parameter `ALL_CAPS` (`DATA_WIDTH`), Enum value `ALL_CAPS` (`ST_IDLE`)

**Why ALL_CAPS only:**
- Mixing CamelCase and snake_case breaks consistency
- `ALL_CAPS` makes constants/parameters visually distinguishable from variables at a glance
- Industry standard (Verilog tradition: ALL_CAPS for parameters)

### Override 5: L_ Prefix for Internal localparam

**lowRISC**: localparam uses the same naming as parameter
**Project**: Non-externally-configurable localparams use `L_` prefix + `ALL_CAPS`

**Why L_ prefix:**
- Immediately distinguishes external parameters (`DATA_WIDTH`) from internal localparams (`L_ADDR_BITS`)
- During code review, instantly answers "can this be changed externally?"
- Example: `L_CNT_MAX = DEPTH - 1` — `DEPTH` is external, `L_CNT_MAX` is an internally derived value

## What Stays the Same

All other lowRISC rules remain in effect:
- `logic` only (no `reg`/`wire`)
- `always_ff` / `always_comb` (no `always`)
- `typedef enum` / `typedef struct packed`
- ANSI port style
- One module per file
- Package-based type sharing
- `unique case` / `priority case`
- 2 spaces indentation, 100 char line length
- `_d` / `_q` suffix for combinational/registered pairs
