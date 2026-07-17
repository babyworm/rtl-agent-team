# rtl-bug-repro Worked Example

`bug-042-cabac-bypass/` shows the two artifacts this skill delivers to
`sim/bugs/{bug_id}/`, for the CABAC bypass-mode failure used throughout
SKILL.md (first divergence at cycle 247 on `u_cabac_encoder.o_bin_val`).

| File | Role |
|------|------|
| `bug-042-cabac-bypass/repro_tb.sv` | Minimal reproduction TB (~100 lines): 2-bin stimulus — one regular-mode bin to prime `bypass_ctx`, one bypass-mode bin to expose the missing reset. Follows `templates/repro-tb-template.sv` structure with all TODO blocks resolved. |
| `bug-042-cabac-bypass/root_cause.md` | Root-cause document per the schema in `references/bug-repro-conventions.md`: symptom, first failure cycle, signal trace, suspected RTL location, reproduction command. |

## What this example demonstrates

- **Minimality**: the failing regression drives thousands of bins; the repro
  TB isolates the failure to two input transitions plus a drain interval.
- **Conventions**: `u_dut` instance, `sys_clk`/`sys_rst_n`, `i_`/`o_`
  prefixes, `logic` types only, `L_` localparams.
- **Exit protocol**: `$finish(0)` when the bug reproduces (expected outcome),
  `$finish(1)` on timeout or non-reproduction — so CI can assert on it.
- **No RTL fix**: the session ends at documentation; the fix belongs to
  `rtl-p4s-bugfix`.

The DUT (`cabac_encoder`) is illustrative — in a real project the TB compiles
against `rtl/cabac_encoder/cabac_encoder.sv` via the `run_sim.sh` command
recorded in `root_cause.md`.
