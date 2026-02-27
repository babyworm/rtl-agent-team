# Verilator Warning Categories and Waiver Format

> This document is the detailed reference for the `rtl-lint-check` skill.
> For core rules, see `<Steps>` in `skills/rtl-lint-check/SKILL.md`.

## 1. Severity Classification

| Severity | Meaning | Default Behavior |
|----------|---------|------------------|
| Error | Non-synthesizable code | Halt, fix required |
| Warning | Potential issue | Displayed, optional fix |
| Info | Informational note | Can be disabled |

## 2. Major Warning Categories

### 2.1 Critical (Must Fix)

| Warning | Meaning | Fix |
|---------|---------|-----|
| `LATCH` | Latch inferred | Add `default` in `always_comb`, assign signal in all paths |
| `COMBDLY` | `<=` used in combinational block | Use `=` (blocking) |
| `BLKSEQ` | `=` used in sequential block | Use `<=` (non-blocking) |
| `MULTIDRIVEN` | Multiple drivers on signal | Restructure to single driver |
| `UNDRIVEN` | Output port undriven | Connect driver or assign `= '0` if intentional |
| `UNUSED` | Input signal unused | Use it or add waiver |
| `WIDTH` | Bit-width mismatch | Explicit cast or adjust bit-width |
| `CASEINCOMPLETE` | Incomplete case statement | Add `default` |

### 2.2 Important (Fix if Possible)

| Warning | Meaning | Fix |
|---------|---------|-----|
| `WIDTHEXPAND` | Auto-expanded | Explicit expansion: `{N{1'b0}, sig}` |
| `WIDTHTRUNC` | Auto-truncated | Explicit truncation: `sig[W-1:0]` |
| `UNSIGNED` | Unsigned comparison caution | Specify `int unsigned` or `$signed()` |
| `SELRANGE` | Possible selection range overflow | Add range check or adjust parameter |
| `IMPLICIT` | Implicit wire declaration | Declare `logic` explicitly |
| `PINMISSING` | Instance port unconnected | Connect port or specify empty connection `.port()` |
| `PINNOCONNECT` | Output port unconnected | Add waiver if intentional, otherwise connect |
| `LITENDIAN` | Mixed big/little endian | Unify to `[MSB:0]` little-endian |

### 2.3 Style (Convention)

| Warning | Meaning | Fix |
|---------|---------|-----|
| `DECLFILENAME` | Filename ≠ module name | Match filename to module name |
| `VARHIDDEN` | Variable shadows upper scope variable | Rename |
| `IMPORTSTAR` | `import pkg::*` | Use explicit import or keep (allowed) |

## 3. Project Convention Checks (Custom)

Project rules not caught by Verilator are inspected by the `lint-checker` agent via grep:

| Rule | Check Pattern | Violation Example |
|------|---------------|-------------------|
| No CamelCase | `parameter\s+int\s+[A-Z][a-z]` | `parameter int DataWidth` |
| No suffix | `\w+_(i|o)\b` in port list | `input logic data_i` |
| No reg/wire | `\breg\b|\bwire\b` | `reg [7:0] data` |
| No always @(*) | `always\s+@\s*\(\s*\*\s*\)` | `always @(*)` |
| No clk_i/rst_ni | `clk_i|rst_ni` | `input logic clk_i` |

## 4. Waiver File Format (.verilator.vlt)

```
// Verilator waiver file
// Format: lint_off -rule WARNING -file "path" [-match "pattern"]

// Intentionally unused signals
lint_off -rule UNUSED -file "rtl/src/my_module.sv" -match "Signal is not used: 'i_debug_*'"

// Intentional bit-width truncation (algorithm requirement)
lint_off -rule WIDTHTRUNC -file "rtl/src/dsp_core.sv" -match "*truncat*"

// Third-party IP (cannot modify)
lint_off -rule WIDTH -file "rtl/ip/*"

// Global: disable specific warning (caution: minimize usage)
// lint_off -rule IMPORTSTAR
```

### Waiver Writing Rules

1. **Prefer per-file waivers** -- minimize global waivers
2. **Use `-match` patterns** -- scope as narrowly as possible
3. **Document reasons in comments** -- why the waiver is needed
4. **Review periodically** -- remove waivers that are no longer necessary

## 5. Verilator Lint Execution Commands

```bash
# Basic lint-only (no simulation)
verilator --lint-only -Wall --top-module my_module rtl/src/my_module.sv

# Include packages
verilator --lint-only -Wall --top-module my_module \
  -y rtl/include/ rtl/src/my_module_pkg.sv rtl/src/my_module.sv

# Apply waivers
verilator --lint-only -Wall --top-module my_module \
  .verilator.vlt rtl/src/my_module.sv

# Use filelist
verilator --lint-only -Wall --top-module top_module -f rtl/filelist.f

# Enable specific warnings only
verilator --lint-only -Wno-fatal -Wwarn-LATCH -Wwarn-WIDTH rtl/src/*.sv
```

## 6. Verilator + Verible Combination

```bash
# Step 1: Verilator (semantic lint)
verilator --lint-only -Wall -f rtl/filelist.f 2>&1 | tee lint_verilator.log

# Step 2: Verible (style lint)
verible-verilog-lint --rules_config .verible.rules rtl/src/*.sv 2>&1 | tee lint_verible.log

# Step 3: slang (IEEE 1800 semantic, optional)
slang --lint-only rtl/src/*.sv 2>&1 | tee lint_slang.log
```
