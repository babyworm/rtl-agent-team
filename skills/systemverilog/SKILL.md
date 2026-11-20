---
name: systemverilog
description: "Project conventions for agents writing SystemVerilog RTL and verification code."
user-invocable: false
---

## Project conventions

Use IEEE 1800-2009 for synthesizable RTL and IEEE 1800-2012 for verification.
The project follows lowRISC style with these naming conventions:

- Prefix ports with `i_`, `o_` or `io_`. Clocks and active-low asynchronous resets use
  `clk` and `rst_n` or `{domain}_clk` and `{domain}_rst_n`.
- Use `snake_case` for modules and signals, `ALL_CAPS` for parameters, macros and enum
  values, and `L_` plus `ALL_CAPS` for local parameters. Use `_e` for enum types and
  `_t` for other typedefs.
- Prefix RTL instances with `u_` and generate blocks with `gen_`. UVM class handles use `m_`.
- Put one module in its matching `.sv` file. Use `*_pkg.sv` for shared types,
  `*_if.sv` for interfaces, `tb_*.sv` for testbenches and `sva_*.sv` for assertion binds.

Use the [module scaffold](templates/module-template.sv) for ANSI ports, declaration order,
`logic`, `always_ff`, `always_comb` and case defaults. Declare types and signals before
their first reference. See the [coding guide](references/coding-style-guide.md) for
detailed RTL conventions and [examples](examples/good-vs-bad.sv) for lint findings.

## Implementing the microarchitecture

Meet the specified throughput, interface latency and operator schedule. Where the schedule
leaves operator count open, share operators across non-overlapping uses while sustaining
the required rate. Prefer registered outputs when the interface budget allows that stage.
Pass dependencies into functions and tasks as arguments. Identify any unavoidable external
reads in the function or task header.

For storage, implement the P3 memory class, dimensions, concurrent accesses, clock domains,
read latency and read-during-write behavior. If an unspecified choice changes the interface or
the design's ability to meet its target, resolve that choice against the project spec and
available memory resources before changing the RTL.

For a specified SRAM wrapper, reuse the matching project module in `rtl/common/` and name
the instance `u_mem_{purpose}`. The [SP](templates/spreg.sv), [TP](templates/tpreg.sv) and
[DP](templates/dpreg.sv) scaffolds have a one-cycle read. SP shares one R/W port. TP and
DP have separate read and write ports with one clock and two clocks respectively.

In the DC/Genus flow, the scaffolds' behavioral arrays are simulation-only. For macro area
and timing, populate the macro branch, enable its guards with `run_syn.sh --mem-process`
(TP/DP also guard on `ASIC_SYNTHESIS`), and link its characterized library with `--mem-lib`.
The runner recognizes `sram_sp`, `sram_tp` and `sram_dp` by default. For other module
names, including the scaffolds' original names, pass `--mem-module <name>`. Verify the
linked cell in the report and identify any blackboxed memory.

## Simulator compatibility

Compile with the simulator and language mode required by the project. For an Icarus
target use `-g2012`. If the installed version rejects an interface port, modport or
unpacked aggregate, use a supported representation that preserves the interface contract.
Limit portability work to the affected target and files.

For a VCS testbench reporting ICPD, check whether an `initial` block or task also writes a
variable assigned in `always_ff`. Give the variable a single writer, or use ordinary
procedural blocks when the testbench needs multiple writers.
