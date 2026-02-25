# Verilator Warning Categories Reference

## Critical Warnings (Must Fix — Functional Risk)

| Warning | Meaning | Fix |
|---------|---------|-----|
| BLKANDNBLK | Mixed blocking/non-blocking assignments to same variable | Use `<=` in `always_ff`, `=` in `always_comb`. Never mix. |
| LATCH | Inferred latch from incomplete combinational logic | Add `default:` to all `case`, add default assignment at top of `always_comb` |
| CASEINCOMPLETE | Case statement missing cases without default | Add `default:` clause or use `unique case` with all values covered |
| MULTIDRIVEN | Multiple drivers on same signal | Ensure signal driven from exactly one `always` block |

## Major Warnings (Synthesizability / Correctness Risk)

| Warning | Meaning | Fix |
|---------|---------|-----|
| WIDTH | Signal width mismatch in assignments/connections | Match widths explicitly; use explicit cast or resize |
| UNDRIVEN | Signal declared but never driven | Drive the signal or remove it |
| SYNCASYNCNET | Signal used both synchronously and asynchronously | Use proper synchronizer or CDC crossing |
| PINCONNECTEMPTY | Module port left unconnected | Connect port or explicitly leave unconnected with comment |
| PINNOCONNECT | Input port has no driver | Connect driver to input |
| UNSIGNED | Unsigned comparison always true/false | Check comparison logic; may need signed cast |
| CMPCONST | Comparison is always true or false | Check bounds; condition may be redundant |
| SELRANGE | Selection index out of range | Fix index bounds |

## Minor Warnings (Style / Best Practice)

| Warning | Meaning | Fix |
|---------|---------|-----|
| UNUSED | Signal declared but never used | Remove unused signal |
| DECLFILENAME | Module name doesn't match filename | Rename file to match module |
| VARHIDDEN | Variable in inner scope hides outer scope | Rename to avoid shadowing |
| IMPORTSTAR | Wildcard import | Use explicit imports |
| DEFPARAM | defparam usage | Use `#()` parameter override instead |

## Recommended Verilator Flags

```bash
# Standard lint check
verilator --lint-only -Wall -Wpedantic -sv rtl/src/*.sv

# Generate waiver template for existing warnings
verilator --lint-only -Wall --waiver-output verilator.vlt rtl/src/*.sv

# Apply waiver file
verilator --lint-only -Wall -Wpedantic rtl/src/*.sv verilator.vlt

# Disable specific warnings (use sparingly, with justification)
verilator --lint-only -Wall -Wno-UNUSED -sv rtl/src/*.sv
```

## Waiver File Format (.vlt)

```
`verilator_config
// Waiver: signal unused intentionally for future expansion
lint_off -rule UNUSED -file "rtl/src/reserved_ports.sv" -lines 10-15
// Waiver: width mismatch is intentional truncation
lint_off -rule WIDTH -file "rtl/src/datapath.sv" -match "Operator *"
```
