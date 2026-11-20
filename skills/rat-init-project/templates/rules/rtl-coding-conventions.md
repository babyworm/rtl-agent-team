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

## Design Style (Preferred)

- **Registered outputs**: drive module outputs directly from a flip-flop. When a register stage is
  needed, register the **output** (compute → FF → output port), not the input followed by
  combinational logic to the port. Registered outputs give consumers a full clock period and keep
  the critical path inside the module (simpler hierarchical timing). Combinational outputs are OK
  for thin glue/passthrough but should be a deliberate choice.
- **Function/task purity**: SV `function`/`task` should use only their arguments. Avoid reading
  module-level signals not passed in (hidden inputs hurt sim sensitivity, synthesis clarity, and
  reuse). If an external dependency is unavoidable, document it in a header comment at the top of
  the function/task (e.g., `// External deps (read): cfg_mode, base_addr`). Prefer passing signals
  as arguments.

## Simulator Compatibility

Use the project's configured simulators and language modes. For an Icarus target, compile
with `-g2012` and check the installed version's support for any interface ports, modports
or unpacked aggregates used by the changed code.

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

## Storage

Follow the P3 memory class, dimensions, concurrent port accesses, read latency, clocks and
specified collision behavior. Use the project's matching wrapper in `rtl/common/` for a
specified SRAM and name the instance `u_mem_{purpose}`. The standard SP, TP and DP scaffolds
all read in one cycle. For DC/Genus macro selection and blackbox handling, see the
`systemverilog` skill.

## Convention Skills (Loaded by Writer Agents)

Convention skills are loaded by writer agents via their `skills:` frontmatter
(rtl-coder→systemverilog, bfm-dev→systemc,
testbench-dev/sva-extractor/protocol-checker→systemverilog-assertion/uvm);
naming basics are also enforced by this rules file on .sv access.

| File Extension / Context | Phase | Convention Skill |
|--------------------------|-------|------------------|
| `.sv`, `.svh`, `.v`, `.vh` (RTL) | Phase 4 (RTL) | `systemverilog` — lowRISC + project overrides, tool caveats, storage selection |
| `.sv`, `.sva` (SVA, assertion, bind) | Phase 5 (Formal) | `systemverilog-assertion` — label naming, bind-file-first, sv2v/SymbiYosys flow |
| `.sv` (UVM testbench) | Phase 5 (UVM) | `uvm` — naming, m_/u_ boundary, RTL port matching, anti-patterns |
| `.cpp`, `.h` (SystemC/TLM) | Phase 2 (Ref Model), Phase 3 (BFM) | `systemc` — naming, bit-exactness, AT-default BFM, build rules |

<!-- rat-version: 2.0.1 -->
