# Yosys Synthesis Command Reference

## Basic Synthesis Flow

```bash
# Generic synthesis (no technology mapping)
yosys -p "read_verilog -sv rtl/*/*.sv; synth -top {top}; stat"

# With flatten for area analysis
yosys -p "read_verilog -sv rtl/*/*.sv; synth -top {top} -flatten; stat"
```

## Technology-Mapped Synthesis

### Sky130 (open-source PDK)
```bash
yosys -p "
  read_verilog -sv rtl/*/*.sv;
  synth -top {top};
  dfflibmap -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
  abc -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
  stat -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
"
```

### NanGate45 (academic PDK)
```bash
yosys -p "
  read_verilog -sv rtl/*/*.sv;
  synth -top {top};
  dfflibmap -liberty NangateOpenCellLibrary_typical.lib;
  abc -liberty NangateOpenCellLibrary_typical.lib;
  stat -liberty NangateOpenCellLibrary_typical.lib;
"
```

## Latch Detection

After synthesis, check for `$_DLATCH_` cells in the stat output:

```
=== design hierarchy ===
   ...
   Number of cells:     1234
     $_DFF_PP0_           42
     $_DLATCH_P_           2   <-- INFERRED LATCHES! Hard error.
     $_MUX_              156
```

**Any `$_DLATCH_` count > 0 is a HARD FAIL.** Latches indicate incomplete combinational logic.

Common causes:
1. Missing `default:` in `case` statement inside `always_comb`
2. Signal not assigned in all branches of `if-else` inside `always_comb`
3. Using `always @(*)` instead of `always_comb` (allows latches silently)

## Key `stat` Output Fields

| Field | Meaning | Concern Level |
|-------|---------|---------------|
| `$_DFF_*` | Flip-flops | Normal (count should match design intent) |
| `$_DLATCH_*` | Latches | **CRITICAL — must be zero** |
| `$_MUX_` | Multiplexers | High count may indicate priority encoding |
| `$_AND_`, `$_OR_` | Logic gates | Normal |
| `$add`, `$mul` | Arithmetic | Check if area-efficient implementation needed |
| `$mem` | Memory blocks | Check if SRAM inference intended |

## Useful Yosys Commands

```tcl
# Show module hierarchy
hierarchy -check -top {top}

# Flatten hierarchy for analysis
flatten

# Optimize
opt; opt_clean; opt_merge

# Write synthesized netlist
write_verilog syn/netlist.v

# Generate dot graph for visualization
show -format dot -prefix syn/schematic

# Check for combinational loops
scc -max_depth 10

# Report timing estimate (logic levels)
tee -q -o syn/reports/timing.txt stat
```

## Synthesis Warnings to Watch

| Warning | Meaning | Action |
|---------|---------|--------|
| "Replacing memory" | RAM inferred | Verify RAM macro matches intent |
| "Cell type not found" | Missing tech library cell | Check library path |
| "Creating latch" | Latch inferred | Fix combinational logic |
| "Inferred tri-state" | Tristate buffer | Verify FPGA target supports tristate |
| "Unconnected signal" | Dead logic | Review RTL for bugs |
