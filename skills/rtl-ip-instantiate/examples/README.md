# rtl-ip-instantiate Worked Example

Two directories show the full skill flow: `scripts/gen_instantiation.py`
produces a deterministic wrapper skeleton from the vendor header, and the
LLM (`rtl-coder`) hand-tunes it into the delivered wrapper.

| Path | Role |
|------|------|
| `vendor_sram_2p/vendor_sram_2p.v` | Vendor IP stub (256x32 two-port SRAM macro, ALL-CAPS ports, active-low chip enables) — the script's input. |
| `vendor_sram_2p/sram_2p_wrapper.sv` | Raw `gen_instantiation.py` output, committed verbatim (regeneration-synced by `tests/unit/test_gen_instantiation.py`). |
| `sram_2p_wrapper/sram_2p_wrapper.sv` | Hand-tuned deliverable: clock domains merged, functional port names, polarity adaptation, documented tie-off reasons. |

## Step 1 — generate the skeleton (deterministic)

```sh
python3 ../scripts/gen_instantiation.py vendor_sram_2p/vendor_sram_2p.v \
    -o vendor_sram_2p/sram_2p_wrapper.sv \
    --tie "EMA=3'b010:vendor-recommended margin setting" \
    --tie "RET1N=1'b1:retention mode not used" \
    --tie "STOV=1'b0:self-time override disabled"
```

The script maps every non-tied vendor port 1:1 to a convention-compliant
wrapper port (`CLKA`→`a_clk`, `CENA`→`i_cena`, `QB`→`o_qb`), passes
parameters through (`W`, `D`), and emits `// TIED:` lines plus the tie-off
documentation table. Ports/params it cannot interpret get `TODO` markers.
Lint check (all pass on the committed output):

```sh
verilator --lint-only -Wall --top-module sram_2p_wrapper \
    vendor_sram_2p/sram_2p_wrapper.sv vendor_sram_2p/vendor_sram_2p.v
```

## Step 2 — hand-tune (LLM/rtl-coder)

`sram_2p_wrapper/sram_2p_wrapper.sv` is the same wrapper after hand-tuning:

- **Clock merge**: `a_clk`/`b_clk` → single `sys_clk` (both macro ports run
  on the system clock in this design) — an interpretive decision the script
  never makes on its own.
- **Functional names**: `i_cena`/`i_aa`/`i_da` → `i_wr_en`/`i_wr_addr`/`i_wr_data`;
  `i_cenb`/`i_ab`/`o_qb` → `i_rd_en`/`i_rd_addr`/`o_rd_data`.
- **Polarity adaptation**: active-low vendor `CENA`/`CENB` driven from
  active-high `i_wr_en`/`i_rd_en` via inversion, documented inline.
- **Parameter rework**: vendor `W`/`D` re-expressed as `DATA_WIDTH`/
  `ADDR_WIDTH` (`D = 2**ADDR_WIDTH`) with real `// PARAM:` descriptions.

The vendor macro (`vendor_sram_2p`) is illustrative — in a real project its
port list comes from the vendor deliverable or the IP-XACT descriptor at
`docs/ip/{ip_name}.xml`, and the wrapper must pass Verible + slang lint
(Execution step 5) before delivery.
