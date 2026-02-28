# SDC Best Practices for RTL Synthesis

## SDC Writing Order (recommended)

Write constraints in this order — later sections may depend on earlier definitions:

1. **Clock definitions** (`create_clock`, `create_generated_clock`)
2. **Clock uncertainty & transition** (`set_clock_uncertainty`, `set_clock_transition`)
3. **Clock relationships** (`set_clock_groups`)
4. **Input/output delays** (`set_input_delay`, `set_output_delay`)
5. **False paths** (`set_false_path`) — with justification
6. **Multicycle paths** (`set_multicycle_path`) — always setup + hold pair
7. **Design rules** (`set_max_fanout`, `set_max_transition`)
8. **Environment** (`set_driving_cell`, `set_load`)

## Critical Rules

### Clock Definitions

| Constraint | When to Use | Project Convention |
|-----------|-------------|-------------------|
| `create_clock` | Primary clock input port | `[get_ports clk]` or `[get_ports sys_clk]` — NOT `clk_i` |
| `create_generated_clock` | PLL/divider output | Must reference master clock with `-source` |

```tcl
# CORRECT — uses project naming convention
create_clock -period 10.0 -name sys_clk [get_ports sys_clk]

# WRONG — non-conformant clock name
create_clock -period 10.0 -name clk [get_ports clk_i]
```

**Every clock in the RTL must have a constraint.** An unconstrained clock means unconstrained paths → timing failures in silicon.

### Clock Uncertainty

Always set uncertainty — even if estimated:

| Component | Typical ASIC | Typical FPGA |
|-----------|-------------|-------------|
| Jitter (source) | 50–200 ps | 100–300 ps |
| Skew (network) | 100–300 ps | 200–500 ps |
| Setup margin | 0.3–0.5 ns total | 0.5–1.0 ns total |
| Hold margin | 0.05–0.15 ns | 0.1–0.3 ns |

### Input/Output Delay Calculation

```
Input delay (max)  = Tclk_q(max, external) + Tboard(max)
Input delay (min)  = Tclk_q(min, external) + Tboard(min)
Output delay (max) = Tsetup(external) + Tboard(max)
Output delay (min) = -Thold(external) + Tboard(min)
```

**Rule of thumb:** If unknown, use 40% of clock period for both input and output max delay.

### False Paths — Justification Required

Every `set_false_path` must have a comment explaining **why** it's false:

| Legitimate False Path | Justification |
|----------------------|---------------|
| Async reset to all | Reset is async assert, sync deassert by design |
| Static config registers | Written only during init, quasi-static during operation |
| Test/scan paths | Not active during functional operation |
| CDC with synchronizer | Handled by `set_clock_groups -asynchronous` |

**Never false-path for convenience.** A false path on a real timing path = silicon failure.

### Multicycle Paths — Always Set Both Setup and Hold

```tcl
# CORRECT — both setup and hold
set_multicycle_path 4 -setup -from [get_cells u_mac/*] -to [get_cells u_mac/o_result_reg*]
set_multicycle_path 3 -hold  -from [get_cells u_mac/*] -to [get_cells u_mac/o_result_reg*]

# WRONG — missing hold MCP (hold will use default = 0, which is wrong)
set_multicycle_path 4 -from [get_cells u_mac/*] -to [get_cells u_mac/o_result_reg*]
```

**MCP formula:**
- Setup MCP = N (number of cycles)
- Hold MCP = N - 1 (standard) or 0 (if data launched from different clock edge)

### Design Rules

| Rule | Typical ASIC Value | Purpose |
|------|-------------------|---------|
| `set_max_fanout` | 16–64 | Prevent excessive wire delay |
| `set_max_transition` | 0.3–0.8 ns | Prevent slow edges (noise, power) |
| `set_max_capacitance` | 0.3–1.0 pF | Protect cell drive strength |

## Common SDC Mistakes

| Mistake | Impact | Fix |
|---------|--------|-----|
| Missing clock definition | Unconstrained paths | Define ALL clocks |
| `set_false_path` without justification | May mask real timing bug | Add comment, verify it's truly false |
| MCP without hold constraint | Hold violations in silicon | Always set both -setup and -hold |
| Using `set_clock_groups` for synchronous clocks | Over-constraining removed | Only for truly asynchronous domains |
| Hardcoded clock period (not parameterized) | Breaks when frequency changes | Reference timing_constraints.json |
| Missing IO delay on ports | Unconstrained I/O timing | Constrain ALL top-level ports |

## SDC Validation Checklist

- [ ] Every clock in RTL has a `create_clock` or `create_generated_clock`
- [ ] Clock uncertainty set for all clocks (setup and hold)
- [ ] Asynchronous clock pairs have `set_clock_groups -asynchronous`
- [ ] All top-level I/O ports have `set_input_delay` / `set_output_delay`
- [ ] Every `set_false_path` has a justification comment
- [ ] Every `set_multicycle_path` has both `-setup` and `-hold`
- [ ] Design rules set (`set_max_fanout`, `set_max_transition`)
- [ ] SDC file passes Tcl syntax check (`tclsh`)
- [ ] Port names use project convention (`sys_clk`, `i_*`, `o_*`)

## Tool-Specific Notes

### Design Compiler (Synopsys)
```tcl
read_file -format sverilog {rtl/*/*.sv}
source constraints/design.sdc
compile_ultra
report_timing -max_paths 10
report_area
```

### Genus (Cadence)
```tcl
read_hdl -sv {rtl/*/*.sv}
elaborate {{TOP_MODULE}}
read_sdc constraints/design.sdc
syn_generic; syn_map; syn_opt
report_timing -nworst 10
report_area
```

### OpenSTA (Open-Source)
```tcl
read_liberty {{LIB_FILE}}
read_verilog syn/netlist/{{MODULE}}_netlist.v
link_design {{TOP_MODULE}}
read_sdc constraints/design.sdc
report_checks -path_delay max -format full
```

### Yosys + OpenSTA Flow
```bash
# Synthesize with Yosys
yosys -p "read_verilog -sv rtl/*/*.sv; synth -top {{TOP}}; \
  write_verilog syn/netlist.v"

# Timing analysis with OpenSTA
sta -exit <<EOF
read_liberty sky130_fd_sc_hd__tt_025C_1v80.lib
read_verilog syn/netlist.v
link_design {{TOP}}
read_sdc constraints/design.sdc
report_checks -path_delay max
report_checks -path_delay min
EOF
```
