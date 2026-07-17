# gen_ipxact.py Worked Example

Demonstrates deterministic IP-XACT generation from a SystemVerilog module
header (Execution step 2 fallback when `sv_to_ipxact` is unavailable).

| File | Role |
|------|------|
| `pixel_fifo.sv` | Input: tiny synchronous FIFO with `i_`/`o_` prefixed ports, `clk`/`rst_n`, and parameterized widths. |
| `pixel_fifo.xml` | Output: IEEE 1685-2014 component XML produced by the command below. |

## Command

Run from this directory:

```sh
python3 ../scripts/gen_ipxact.py pixel_fifo.sv -o pixel_fifo.xml \
    --vendor rtl_team --library video_lib
```

Expected report:

```
Generated pixel_fifo.xml: module=pixel_fifo ports=9 (vector=3, scalar=6) parameters=2 vlnv=rtl_team:video_lib:pixel_fifo:1.0
Well-formedness check: PASS (xml.etree re-parse)
```

## What to check in the output

- Port names are verbatim (prefix preserved): `i_wr_data`, `o_rd_valid`, ...
- Direction derives from the `input`/`output`/`inout` keyword: `in`/`out`/`inout`.
- Parameterized widths stay expressions — `i_wr_data` carries
  `<ipxact:left>DATA_WIDTH-1</ipxact:left>`, `o_level` carries
  `$clog2(DEPTH)` — never resolved to literals (see
  `references/ipxact-conventions.md` anti-patterns).
- `clk`/`rst_n` get clock/reset role descriptions (prefix-exempt ports).
- Parameters `DATA_WIDTH`/`DEPTH` appear with their default values.
- No `busInterfaces`/`memoryMaps`: interpretive bus classification and
  register map inference are the `ipxact-generator` agent's job per the
  skill's `<Responsibility_Boundary>`; the script emits only deterministic
  content.
