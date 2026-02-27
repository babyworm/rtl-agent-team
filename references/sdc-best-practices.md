# SDC (Synopsys Design Constraints) Best Practices

> This document is the detailed reference for the `synth-check` skill.
> For core rules, see `<Steps>` in `skills/synth-check/SKILL.md`.
> SDC template: `skills/synth-check/templates/design-constraints.sdc`

## 1. SDC Basic Rules

### 1.1 Clock Definition

```tcl
# Single clock
create_clock -period 10.0 -name sys_clk [get_ports sys_clk]

# Multiple clock domains
create_clock -period 10.0 -name sys_clk   [get_ports sys_clk]
create_clock -period  6.6 -name pixel_clk [get_ports pixel_clk]

# Generated clock (PLL/MMCM output)
create_generated_clock -name pll_clk_2x \
  -source [get_ports sys_clk] \
  -multiply_by 2 \
  [get_pins u_pll/clk_out]
```

### 1.2 Port Naming Rules (Follow Project Convention)

```tcl
# Port names must exactly match RTL
# Project rules: {domain}_clk, {domain}_rst_n, i_/o_ prefix

# CORRECT
set_input_delay -clock sys_clk -max 3.0 [get_ports i_data*]
set_output_delay -clock sys_clk -max 2.0 [get_ports o_result*]

# WRONG (suffix convention)
# set_input_delay -clock clk_i -max 3.0 [get_ports data_i*]
```

## 2. Input/Output Delay

### 2.1 Input Delay

```tcl
# Delay from external FF to current design input
# max: for setup analysis, min: for hold analysis
set_input_delay -clock sys_clk -max 3.0 [get_ports i_data*]
set_input_delay -clock sys_clk -min 0.5 [get_ports i_data*]
set_input_delay -clock sys_clk -max 3.0 [get_ports i_valid]
set_input_delay -clock sys_clk -min 0.5 [get_ports i_valid]

# DDR input (both edges)
set_input_delay -clock sys_clk -max 2.0 [get_ports i_ddr_data*]
set_input_delay -clock sys_clk -max 2.0 -clock_fall -add_delay [get_ports i_ddr_data*]
```

### 2.2 Output Delay

```tcl
# Required time from current design output to external FF setup
set_output_delay -clock sys_clk -max 2.0 [get_ports o_result*]
set_output_delay -clock sys_clk -min 0.3 [get_ports o_result*]
```

### 2.3 Calculation Formulas

```
Input delay max  = Tclk_to_q(external) + Tboard_delay
Input delay min  = Tclk_to_q_min(external)
Output delay max = Tsetup(external) + Tboard_delay
Output delay min = -Thold(external)
```

## 3. Clock Uncertainty & Transition

```tcl
# Setup uncertainty (jitter + skew)
set_clock_uncertainty -setup 0.3 [get_clocks sys_clk]
# Hold uncertainty
set_clock_uncertainty -hold  0.1 [get_clocks sys_clk]

# Clock transition (slew rate)
set_clock_transition 0.15 [get_clocks sys_clk]
```

## 4. False Path & Multicycle

### 4.1 False Path

```tcl
# Asynchronous reset → false path
set_false_path -from [get_ports sys_rst_n]

# CDC path (handled by 2-FF synchronizer)
set_false_path -from [get_clocks sys_clk] -to [get_clocks pixel_clk]
set_false_path -from [get_clocks pixel_clk] -to [get_clocks sys_clk]

# Configuration registers (rarely changes)
set_false_path -from [get_cells u_config/cfg_reg*]
```

### 4.2 Multicycle Path

```tcl
# 2-cycle operation (e.g., multiplier)
set_multicycle_path 2 -setup -from [get_cells u_mul/stage1_q*] -to [get_cells u_mul/result_q*]
set_multicycle_path 1 -hold  -from [get_cells u_mul/stage1_q*] -to [get_cells u_mul/result_q*]
```

### 4.3 Cautions

| Item | Description |
|------|-------------|
| Do not overuse false path | Marking actual functional paths as false path causes undetected timing violations |
| CDC should be false path | However, a synchronizer must exist |
| Multicycle hold | `-hold` value is typically `-setup` value - 1 |

## 5. Clock Groups

```tcl
# Asynchronous clock groups (mutual false path)
set_clock_groups -asynchronous \
  -group [get_clocks sys_clk] \
  -group [get_clocks pixel_clk]

# Exclusive clocks (MUX-selected, cannot be active simultaneously)
set_clock_groups -physically_exclusive \
  -group [get_clocks pll_clk_fast] \
  -group [get_clocks pll_clk_slow]
```

## 6. Tool-Specific Differences

| Feature | Synopsys DC | Cadence Genus | Yosys |
|---------|------------|---------------|-------|
| SDC support | Full | Full | Partial |
| `create_clock` | O | O | O |
| `set_input_delay` | O | O | O (limited) |
| `set_false_path` | O | O | X (comment only) |
| `set_multicycle_path` | O | O | X |
| `set_clock_groups` | O | O | X |

Yosys only partially supports `create_clock`, `set_input_delay`, and `set_output_delay`.
False path and multicycle are documented as comments, and actual application is done at the P&R tool stage.

## 7. SDC Verification Checklist

- [ ] `create_clock` defined for all clock ports
- [ ] `create_generated_clock` for generated clocks (PLL/MMCM)
- [ ] `set_input_delay` for all input ports (max + min)
- [ ] `set_output_delay` for all output ports (max + min)
- [ ] `set_false_path` for asynchronous resets
- [ ] `set_false_path` or `set_clock_groups` for CDC paths
- [ ] Clock uncertainty configured
- [ ] Port names match RTL (i_/o_ prefix, sys_clk, etc.)
