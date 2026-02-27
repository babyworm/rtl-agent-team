# Yosys Command Reference and Latch Detection Guide

> This document is the detailed reference for the `synth-check` skill.
> For core rules, see `<Steps>` in `skills/synth-check/SKILL.md`.

## 1. Yosys Basic Synthesis Flow

```tcl
# === 1. Read Design ===
read_verilog -sv rtl/src/my_module_pkg.sv
read_verilog -sv rtl/src/my_module.sv

# === 2. Elaborate ===
hierarchy -top my_module -check

# === 3. Pre-Synthesis Checks ===
check -assert                    # Basic consistency check
proc                             # Process always blocks → muxes/FFs
flatten                          # Flatten hierarchy (optional)

# === 4. Synthesize ===
synth -top my_module             # Generic synthesis
# OR target-specific:
# synth_xilinx -top my_module   # Xilinx FPGA
# synth_ice40 -top my_module    # iCE40 FPGA

# === 5. Post-Synthesis Analysis ===
stat                             # Area/resource report
check -assert                    # Final consistency check

# === 6. Write Output ===
write_verilog -noattr synth/netlist.v
write_json synth/netlist.json
```

## 2. Latch Detection

### 2.1 Latch Check Commands

```tcl
# Check for latches after proc
proc
# If Yosys generates $_DLATCH_ cells, latches are present

# Method 1: Count latches in stat
stat
# Output: "$_DLATCH_P_  2" ← 2 latches present

# Method 2: Search for latch cells via select
select -module my_module t:$_DLATCH_*
stat                    # Count of selected latch cells

# Method 3: Search in JSON output
write_json -noattr /dev/stdout | grep -i dlatch
```

### 2.2 Latch Causes and Fixes

| Cause | Example | Fix |
|-------|---------|-----|
| Incomplete `case` | `case` without `default` | Add `default` branch |
| Incomplete `if/else` | `if` without `else` | Add `else` branch |
| Partial assignment in `always_comb` | Assignment only under certain conditions | Assign in all paths |
| Feedback without async reset | `always @(*)` with state | Use `always_ff` + reset |

```systemverilog
// LATCH (WRONG):
always_comb begin
  if (sel) out = in_a;
  // no else → latch!
end

// NO LATCH (CORRECT):
always_comb begin
  out = '0;            // default value
  if (sel) out = in_a;
end
```

## 3. Key Yosys Command Reference

### 3.1 Read & Elaborate

| Command | Purpose | Example |
|---------|---------|---------|
| `read_verilog -sv` | Read SystemVerilog | `read_verilog -sv file.sv` |
| `read_verilog -D MACRO=1` | Set define | `read_verilog -D SYNTH=1 file.sv` |
| `hierarchy -top` | Specify top module | `hierarchy -top my_top -check` |
| `hierarchy -check` | Check unresolved references | Detect unresolved module errors |

### 3.2 Synthesis Passes

| Command | Purpose | Notes |
|---------|---------|-------|
| `proc` | always → logic cells | Infers FF, mux, latch |
| `opt` | General optimization | Dead code removal, const folding |
| `opt_clean` | Remove unused cells/wires | |
| `flatten` | Remove hierarchy | Improves area report accuracy |
| `memory` | Memory inference | Determines BRAM/distributed |
| `techmap` | Technology mapping | generic → target cells |
| `abc` | Logic optimization (ABC) | Area/speed optimization |
| `dfflibmap` | FF library mapping | Map to target FF cells |

### 3.3 Analysis & Reporting

| Command | Purpose | Output Example |
|---------|---------|----------------|
| `stat` | Resource count | cells, wires, FF count |
| `stat -tech` | Technology-specific resources | LUT, FF, BRAM (FPGA) |
| `check` | Consistency check | combinational loops, etc. |
| `tee -o file.log stat` | Output to file | Generate log file |
| `show` | Circuit diagram (dot) | GraphViz visualization |
| `write_json` | JSON netlist | For post-processing |

### 3.4 Selection

```tcl
# Select only cells of a specific module
select -module my_module

# Select only FF cells
select t:$dff t:$adff t:$sdff

# Select only latch cells
select t:$dlatch t:$_DLATCH_*

# Stat after selection
select t:$dff; stat; select -clear
```

## 4. FPGA Target-Specific Synthesis

### 4.1 Xilinx

```tcl
read_verilog -sv rtl/src/*.sv
synth_xilinx -top my_module -family xc7
stat
write_verilog -noattr synth/xilinx_netlist.v
```

### 4.2 iCE40

```tcl
read_verilog -sv rtl/src/*.sv
synth_ice40 -top my_module
stat
write_blif synth/ice40_netlist.blif
```

### 4.3 ECP5

```tcl
read_verilog -sv rtl/src/*.sv
synth_ecp5 -top my_module
stat
write_json synth/ecp5_netlist.json
```

## 5. Common Yosys Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `ERROR: Module not found` | Top module name mismatch | Verify `-top` argument |
| `ERROR: Identifier not found` | Missing import | Add `import pkg::*` |
| `Warning: Latch inferred` | Incomplete combinational logic | Add default assignment |
| `ERROR: syntax error` | Unsupported SV syntax | Verify `-sv` flag, check Yosys SV support scope |
| `Warning: Replacing memory` | Memory inference failure | Verify synchronous read pattern |

## 6. Synthesis Script Template

See `skills/synth-check/templates/yosys-synth-script.ys`.
