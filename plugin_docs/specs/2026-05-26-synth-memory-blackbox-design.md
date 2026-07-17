# Synthesis Memory Blackbox + Compiler-Macro Placeholder — Design

- Date: 2026-05-26
- Status: Implemented (historical design record)
- Scope: `run_syn.sh` (DC/Genus) + SRAM wrapper convention + synthesis docs

> **Historical boundary:** This document preserves the implemented design rationale.
> Present-tense proposals and checklists below are a record of that implementation,
> not pending work or the current operational source of truth.

## Problem

Behavioral memory in RTL is written as a 2-D array (`logic [W-1:0] mem [0:D-1]`),
which is correct for **simulation** but, when handed to Design Compiler / Genus,
is elaborated into a flip-flop bank. For real memory sizes this:

1. Explodes runtime (the user observed synthesis stalling on the array).
2. Produces meaningless area/timing (flops instead of a compiled SRAM macro).

The plugin already documents a wrapper convention (`sram_sp/tp/dp` in `rtl/common/`,
`u_mem_` instances — `skills/systemverilog/SKILL.md` A.2), but the synthesis side
only has a **commented-out `set_dont_touch`** stub (which does NOT prevent elaboration
of the array), and there is no warning when a behavioral memory reaches synthesis.

## Goals

1. A behavioral memory array MUST NOT be elaborated into flops by DC/Genus.
2. With no compiled macro, the memory is effectively **blackboxed** and its boundary is
   excluded from timing, so synthesis is fast and STA does not propagate through it.
3. A **warning** (and optional `--mem-strict` failure) fires whenever the elaborated design
   contains a memory-wrapper cell that is blackboxed (no compiled macro) — emitted by the
   synthesis tool itself, gated on `get_cells` (instantiation-aware, not a source-file scan).
4. A wrapper provides an in-RTL **placeholder** where a process-specific compiled macro
   can be instantiated (active only during synthesis).

## Key Mechanism — `synopsys translate_off` (RTL-self-contained)

Wrapping the behavioral model body in `// synopsys translate_off` … `// synopsys
translate_on` makes DC and Genus **skip it during synthesis** (simulators ignore the
pragma and still run it). The wrapper then has ports but no synthesizable body → an
**empty module**, so the 2-D array is never elaborated (root-cause fix for the slowness).

This moves the "exclude from synthesis" decision **into the RTL**, so `run_syn.sh` needs
**no awk file-exclusion and no emptiness inference**. Its job reduces to **timing/boundary
handling** on the memory cells, plus optional macro wiring.

Nuance: `translate_off` yields an *empty module* (undriven outputs), not a library-backed
blackbox. `run_syn.sh` therefore adds `set_dont_touch` (keep the empty hierarchy; prevent
optimize-away / constant propagation) + `set_disable_timing` (ignore the boundary) so the
empty memory behaves as a clean blackbox for estimation.

## Non-Goals

- Yosys: infers `$mem` cells (fast, not flops) and has its own memory flow. Out of scope
  for blackbox handling; the unguarded-array warning still applies to all tools.
- Shipping foundry macro libraries or actual `sram_*.sv` files (the plugin documents the
  convention; projects author the wrappers).
- Automatic wrapper-port ↔ vendor-macro-pin mapping (guided by commented examples only).

## Architecture — Responsibility Split

| Layer | Responsibility |
|-------|----------------|
| **RTL wrapper** (`systemverilog` A.2 convention) | Behavioral model body wrapped in `// synopsys translate_off`/`translate_on` (auto-skipped by synth → empty module). Optional `` `ifdef <PROCESS> `` branch instantiates a real compiled macro (active only when the synth define is set). |
| **`run_syn.sh`** | Apply `set_dont_touch` + `set_disable_timing` to memory cells (the "timing handling"). Pass `--mem-process` → `+define+<NAME>` to activate a macro branch; link `--mem-lib` for real macro timing. The blackbox + WARNING + `--mem-strict` failure are emitted into the generated Tcl, gated on `get_cells` finding real (instantiated) memory cells — instantiation-aware, not a source-file scan. |

## RTL Wrapper Convention (systemverilog A.2 update)

```systemverilog
module sram_sp #(parameter int DEPTH = 256, WIDTH = 32) (
  input  logic                     clk, i_ce, i_we,
  input  logic [$clog2(DEPTH)-1:0] i_addr,
  input  logic [WIDTH-1:0]         i_wdata,
  output logic [WIDTH-1:0]         o_rdata
);
`ifdef RAT_MEM_TSMC_N22
  // ── TSMC N22 compiled SRAM — replace with the real macro + pin map ──
  // TS1N22ULLSBLVTC256X32M4SWBASO u_macro (
  //   .CLK(clk), .CEB(~i_ce), .WEB(~i_we), .A(i_addr), .D(i_wdata), .Q(o_rdata));
`elsif RAT_MEM_SKY130
  // ── SkyWater 130 compiled SRAM ──
  // sky130_sram_1rw1r_... u_macro ( ... );
`else
  // ── Behavioral model — SIMULATION ONLY (skipped at synthesis) ──
  // synopsys translate_off
  logic [WIDTH-1:0] mem [0:DEPTH-1];
  always_ff @(posedge clk) if (i_ce) begin
    if (i_we) mem[i_addr] <= i_wdata;
    o_rdata <= mem[i_addr];
  end
  // synopsys translate_on
`endif
endmodule
```

- **Simulation** (no synth define): `` `else `` behavioral runs; `translate_off` is ignored by simulators. ✓
- **Synthesis, no macro**: `` `else `` body is `translate_off`'d → empty module → fast, no flop array. `run_syn.sh` makes it a clean blackbox boundary. ✓
- **Synthesis, macro selected** (`--mem-process RAT_MEM_TSMC_N22`): the macro branch is synthesized; link the macro via `--mem-lib`. ✓

Same pattern for `sram_tp` / `sram_dp`.

## run_syn.sh — Synthesis Handling (DC + Genus)

1. **Identify memory cells.** Cells whose `ref_name` matches a recognized wrapper module
   (`sram_sp`/`sram_tp`/`sram_dp`, plus any `--mem-module` names) via `ref_name =~ <name>*` globs.
   Detection is on the ELABORATED design (`get_cells`), not a source scan — instantiation-aware.
2. **Timing/boundary handling** (emitted into the generated Tcl, before compile, gated on
   `get_cells` finding cells):
   - DC: `set _mem_cells [get_cells -quiet -hierarchical -filter {ref_name =~ sram_sp* || ...}]`;
     if non-empty → `set_dont_touch` + `set_disable_timing`.
   - Genus: same filter (catch-guarded) → `set_dont_touch` + `set_disable_timing`.
3. **Macro selection (optional).** `--mem-process <NAME>` → `+define+<NAME>` on `analyze`/`read_hdl`
   to activate the `` `ifdef `` branch. `--mem-lib <file.db|.lib>` → link the compiled macro
   (DC: link_library/read_db; Genus: read_libs) for real timing/area (then no disable_timing on it).
4. **Blackboxed-memory warning + `--mem-strict` (Tcl-driven, instantiation-aware).** Emitted
   INTO the generated Tcl, inside the `get_cells` block, so they fire only when the ELABORATED
   design actually contains memory cells — NOT from a shell-side file scan. A shell `grep` of
   the sources cannot tell a module *declaration* from an *instantiation*, and would false-warn /
   false-fail on a declared-but-unused wrapper (or one defined in `rtl/common` but not
   instantiated by this top), and could match commented-out `module` lines. So detection lives
   where it is accurate: `get_cells`. When blackboxed — i.e. NOT (both `--mem-process` and
   `--mem-lib` given) — and `sizeof_collection $_mem_cells > 0`:
   `puts "WARNING: N memory wrapper cell(s) blackboxed — no compiled macro (timing disabled).`
   `Provide --mem-process + --mem-lib for real timing/area."` With `--mem-strict`, the Tcl also
   emits `exit 1`, so a real DC/Genus run fails (fake-tool unit tests assert the Tcl *contains*
   the strict construct). This is the "memory model should have been swapped in but wasn't"
   signal, printed by the synthesis tool itself (the user's "especially in the tool" request).
   Wrappers with an active macro (both `--mem-process` and `--mem-lib`) are not blackboxed/warned;
   LUT/ROM arrays elsewhere never match the `ref_name =~ sram_*` filter (no false positives).

## New `run_syn.sh` Flags

| Flag | Meaning | Default |
|------|---------|---------|
| `--mem-process <NAME>` | Inject `+define+<NAME>` (activates the wrapper `` `ifdef `` branch). Repeatable. | none |
| `--mem-lib <file.db\|.lib>` | Compiled-macro timing library to link. | none |
| `--mem-module <name[,name]>` | Extra wrapper module names (matched by `ref_name`) beyond `sram_sp/tp/dp`. | none |
| `--mem-strict` | Promote the blackboxed-memory WARNING to an error (signoff runs). | off |

Scope: DC + Genus. Yosys keeps native memory inference.

## Files Changed

- `skills/rat-init-project/templates/run_syn.sh` — memory-cell `set_dont_touch`/`set_disable_timing`
  emission (DC + Genus, gated on `get_cells`), `+define+` injection, `--mem-lib` link, new flags,
  Tcl-emitted blackbox WARNING + `--mem-strict`; replace the commented `set_dont_touch` stub; bump
  `# rat-version`.
- `skills/syn-tool-profiles/SKILL.md` — document the flags + translate_off blackbox behaviour.
- `skills/systemverilog/SKILL.md` — A.2 wrapper examples → `translate_off` + `` `ifdef `` pattern.
- `skills/rat-init-project/templates/rules/rtl-coding-conventions.md` — one line: behavioral memory
  must be `translate_off`-guarded or a compiled macro.
- `tests/unit/` — see Test Plan.

## Test Plan

1. **DC/Genus memory cells** present → generated Tcl contains `set_dont_touch` + `set_disable_timing`
   for the memory refs/instances (fake-tool harness; assert on generated script).
2. **`--mem-process P`** → `+define+P` appears on `analyze`/`read_hdl` lines.
3. **`--mem-lib L`** → link of `L` emitted (and the macro is not disable_timing'd).
4. **Blackbox (no `--mem-lib`)** → generated Tcl has the `get_cells` filter + `set_dont_touch` +
   `set_disable_timing` + the WARNING `puts` (warning lives in the Tcl, not shell stderr).
5. **Macro active** (`--mem-process P` + `--mem-lib`) → `+define+P` + lib linked in setup; no
   `get_cells` blackbox block emitted.
6. **`--mem-strict`** → generated Tcl contains the strict `exit 1` construct (gated on `get_cells`);
   a design with NO memory does not shell-fail (instantiation-aware — Codex R1-F1).
7. **`bash -n`** + existing `test_eda_replay_and_commercial.py` DC/Genus paths still pass.

## Edge Cases / Risks

- **Pragma spelling**: the RTL convention uses `// synopsys translate_off` (DC + Genus-compatible).
  The blackbox decision does not parse the pragma — `get_cells` finds the wrapper cell regardless;
  translate_off only governs whether the tool elaborates the behavioral array into flops.
- **Empty module undriven outputs**: handled by `set_dont_touch` (keep hierarchy) — without it DC
  may optimize the empty instance away or constant-propagate undriven outputs into the parent.
- **`set_disable_timing` on an empty cell** is harmless (no arcs); it matters once a macro/blackbox
  with arcs is present and for keeping STA from flagging the memory boundary.
- **Scope = recognized wrappers only**: the warning is wrapper-scoped, so LUT/ROM-style arrays
  elsewhere never trigger it (no false positives). Advisory by default; `--mem-strict` to enforce.
- **Genus pragma**: Genus honors `// synopsys translate_off` for compatibility; documented.
- **Tcl-unsafe inputs**: DC/Genus emit all paths (project/synth root, source files, `rtl/common`,
  `--liberty`, `--sdc`, `--mem-lib`) and `--top` into Tcl. Before generation, run_syn.sh rejects
  any finalized path containing Tcl-active characters (`[ ] { } $ ; " ` \`) and requires `--top`,
  `--mem-process`, `--mem-module` to be plain identifiers — preventing Tcl injection/breakage.
