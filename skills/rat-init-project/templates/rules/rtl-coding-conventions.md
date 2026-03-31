---
paths:
  - "rtl/**/*.sv"
  - "rtl/**/*.svh"
  - "rtl/**/*.v"
  - "rtl/**/*.vh"
---

# RTL Coding Conventions

These rules apply only to RTL source code under `rtl/`. Verification code (UVM, cocotb TB in `sim/`) follows its own practices.

## Language Standards

| Language | Standard | Notes |
|----------|----------|-------|
| **SystemVerilog (RTL)** | **IEEE 1800-2009** | Baseline for synthesizable RTL. Post-2012 features are verification-only |
| **SystemVerilog (Verification)** | **IEEE 1800-2012** | 2012 features allowed in SVA, UVM TB (checker, interface class, etc.) |
| **C (Ref Model)** | **C11** (`-std=c11`) | DPI-C priority. Functional model (no clock/reset). External memory abstraction required |
| **C++ (BFM, SystemC)** | **C++17** (`-std=c++17`) | SystemC 3.0 TLM-2.0 BFM only. Not for ref model |

## Core Overrides (Always Applied)

1. **Port prefix**: `i_`, `o_`, `io_` required (NOT suffix `_i`, `_o`). **Clock and reset are exceptions** (no prefix)
2. **Clock**: `clk` (single) or `{domain}_clk` (multiple, e.g., `sys_clk`) — NOT `clk_i`
3. **Reset**: `rst_n` (single) or `{domain}_rst_n` (multiple, e.g., `sys_rst_n`) — Active-low async. NOT `rst_ni`
4. **CamelCase prohibited**: Parameter → `ALL_CAPS` (`DATA_WIDTH`). localparam → `L_` prefix (`L_ADDR_BITS`). Enum → `ALL_CAPS` (`ST_IDLE`). Only `snake_case` or `ALL_CAPS`
5. **UVM exception**: `m_` prefix allowed for UVM class internal member handles. `u_` is for RTL instances only

## iverilog Limitations

- Flag: `-g2012` (basic SV syntax support)
- **Unsupported**: `interface`, unpacked `struct`/`union` — agents must not generate these
- `typedef struct packed` / `typedef union packed` are supported (usable)
- Do not modify if user has added them directly or they exist in existing code
- verilator/slang fully support 2009 features with default settings
- No synthesis-related feature additions after 2012 (2017 is errata only, 2023 has early tool support)

## Declaration Ordering (IEEE 1800 §12.5)

- **All identifiers must be declared before first use** within a module body
- Xcelium (xmvlog) strictly enforces sequential declaration visibility; Verilator/iverilog may be lenient
- Required order within a module:
  1. `import` / `typedef` / `localparam` / `enum`
  2. Signal declarations (`logic`)
  3. `assign` continuous assignments
  4. Submodule instances (`u_` prefix)
  5. `always_comb` / `always_ff` blocks
- Reordering concurrent RTL statements has zero synthesis impact, but **declarations must precede usage**

## Storage Selection (Register vs SRAM Wrapper)

| Total Bits | Ports | Implementation |
|-----------|-------|---------------|
| ≤256 | any | Flip-flop array (`logic [W-1:0] name [0:D-1]`) |
| 257–4096, ≤2 R/W | ≤2 | `sram_sp` / `sram_tp` wrapper from `rtl/common/` (recommended) |
| >4096, ≤2 R/W | ≤2 | `sram_sp` / `sram_tp` wrapper (mandatory) |
| any, >2 R/W | >2 | Flip-flop array (multi-port register file) |

- Exceptions: non-zero reset, partial-word RMW, clock-gating survival → register file with documented rationale
- SRAM wrapper naming: `sram_sp.sv`, `sram_tp.sv`, `sram_dp.sv` in `rtl/common/`
- SRAM instance prefix: `u_mem_` (e.g., `u_mem_coeff`, `u_mem_line_buf`)
- Wrapper parameters: `DEPTH`, `WIDTH` (derived `ADDR_W = $clog2(DEPTH)` inside wrapper)
- SP ports: `clk`, `i_ce`, `i_we`, `i_addr`, `i_wdata`, `o_rdata` (1-cycle read latency)
- Behavioral for simulation; foundry macro swap via `` `ifdef SYNTHESIS `` guard inside wrapper

## Convention Skills (Auto-Applied by Extension/Phase)

| File Extension / Context | Phase | Applied Skill |
|--------------------------|-------|---------------|
| `.sv`, `.svh`, `.v`, `.vh` (RTL) | Phase 4 (RTL) | `/rtl-agent-team:systemverilog` |
| `.sv`, `.sva` (SVA, assertion, bind) | Phase 5 (Formal) | `/rtl-agent-team:systemverilog-assertion` |
| `.sv` (UVM testbench) | Phase 5 (UVM) | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM) | Phase 2 (Ref Model), Phase 3 (BFM) | `/rtl-agent-team:systemc` |

- `systemverilog`: lowRISC + overrides, Power optimization, FPGA, Pipelining
- `systemverilog-assertion`: SVA patterns, bind files, SymbiYosys integration, assume/assert/cover
- `uvm`: UVM class hierarchy, factory, TLM ports, coverage, phase callback
- `systemc`: TLM-2.0 AT non-blocking, AMBA-PV (AXI/AHB/APB), Memory Manager, PEQ, cocotb integration

<!-- rat-version: 0.7.7 -->
