# Bug BUG-042 — Root Cause Analysis

## Symptom
Regression test `test_cabac_bypass` reports `o_bin_val` mismatch: bypass-mode
bin encodes as `1` where the reference model produces `0`.

## First Failure Cycle
Cycle 247: signal `u_cabac_encoder.o_bin_val` expected `0`, got `1`.

## Signal Trace
| Cycle | `i_bypass_en` | `i_bin` | `u_dut.bypass_ctx` | `o_bin_val` | Note |
|-------|---------------|---------|--------------------|-------------|------|
| 8     | 0             | 1       | 1 (loaded)         | —           | regular-mode bin primes context |
| 246   | 1             | 0       | 1 (stale)          | —           | bypass bin accepted |
| 247   | 1             | 0       | 1 (stale)          | 1 (wrong)   | stale context drives output |

## Suspected Root Cause
`rtl/cabac_encoder/cabac_encoder.sv`, line 183: `bypass_ctx` register is not
cleared when `i_bypass_en` asserts, so the first bypass-mode bin after a
regular-mode bin reuses the stale context value instead of the raw bin.

## Clock / Reset Context
Clock domain: `sys_clk`. Reset: `sys_rst_n` (active-low async). Bug is not
reset-related — it reproduces after clean reset with a 2-bin stimulus.

## Reproduction Confirmed
repro_tb.sv reproduces failure at cycle 247. Run:
`scripts/run_sim.sh --sim iverilog --top repro_tb --outdir sim/bugs/BUG-042 --trace rtl/cabac_encoder/cabac_encoder.sv sim/bugs/BUG-042/repro_tb.sv`
