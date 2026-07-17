# check_connectivity.py Worked Example

Demonstrates the Tier 4 static connectivity check (Execution step 3, run
before any dynamic simulation) on a 3-module hierarchy with two intentional
bugs.

| File | Role |
|------|------|
| `dut_top.sv` | Top module with TWO INTENTIONAL BUGS: an 8-bit `pix` signal connected to the 16-bit `i_data` port (width mismatch), and `o_word_valid` of `u_pack` left explicitly unconnected (dangling port). |
| `pixel_gen.sv` | Submodule 1 (clean): pattern generator, `PIX_W` parameterized output. |
| `pixel_pack.sv` | Submodule 2 (clean): packs two `DATA_W` samples into one `WORD_W` word. |
| `dut_top_connectivity.json` | Output: JSON report produced by the command below — exactly 1 error (`width_mismatch`) + 1 warning (`dangling_port`), verdict FAIL. |

## Command

Run from this directory:

```sh
python3 ../scripts/check_connectivity.py dut_top.sv pixel_gen.sv pixel_pack.sv \
    -o dut_top_connectivity.json
```

Expected report (exit 1 — verdict FAIL):

```
Wrote dut_top_connectivity.json: verdict=FAIL errors=1 warnings=1
```

## What to check in the output

- `width_mismatch` (error, dut_top.sv:29): `pixel_pack.i_data` resolves to
  width 16 from the parameter default `DATA_W = 16`; the connected signal
  `pix` is `[7:0]` → 8. Parameter-resolvable widths are checked, not just
  literals (`u_gen`'s `PIX_W(8)` override is resolved too — no false
  positive on `o_pix`).
- `dangling_port` (warning, dut_top.sv:32): explicitly empty `.o_word_valid()`.
  Output pins rate a warning; an empty *input* pin would be an error
  (undriven input).
- `summary.width_checks`: 10 checked, 0 skipped — every connection in this
  example is literal/parameter resolvable.
- No `undriven_output`: the top `o_word_valid` is driven by the trailing
  `assign`, and `o_word` by an instance output.
- Cross-validation: `verilator --lint-only -Wall --top-module dut_top
  dut_top.sv pixel_gen.sv pixel_pack.sv` flags exactly the same two spots
  (`WIDTHEXPAND` at :29, `PINCONNECTEMPTY` at :32); the submodules lint
  clean individually.
- No timestamps: re-running the command reproduces the committed JSON
  byte-for-byte (locked by `tests/unit/test_check_connectivity.py`).
