---
name: systemverilog
description: "systemverilog project conventions (loaded by writer agents; do not invoke)."
user-invocable: false
---

<Purpose>
Project-specific SystemVerilog conventions and tool caveats for all .sv/.v generation.
Baseline style: lowRISC SystemVerilog Coding Style Guide — this skill covers ONLY the project
overrides and tool-specific rules layered on top of it. Naming basics are additionally enforced
by the deployed `.claude/rules/rtl-coding-conventions.md` (rat-init-project) on .sv access.

Language standard pins:
- Synthesizable RTL: **IEEE 1800-2009** (iverilog parses with `-g2012` — the 2012 parser handles 2009 code)
- SV verification code: **IEEE 1800-2012**
- 2012+ features (checker, interface class, let, soft constraint) are verification-only — never in RTL
</Purpose>

<Use_When>
- Writing or modifying .sv, .svh, .v, .vh files (Phase 4 RTL; Phase 5 SV TB/SVA)
- Agents: rtl-coder, sva-extractor, testbench-dev, lint-checker, ppa-optimizer-dc
</Use_When>

<Do_Not_Use_When>
- SystemC/C++ code → `systemc` skill; Python cocotb tests → `rtl-p5s-func-verify` skill; documentation-only work
</Do_Not_Use_When>

<Execution_Policy>
- Violations produce a FAIL verdict from the rtl-lint-check skill
- New module scaffold: `templates/module-template.sv`; correct/incorrect patterns: `examples/good-vs-bad.sv`
- Detailed override rationale vs. original lowRISC rules: `references/coding-style-guide.md`
</Execution_Policy>

<Steps>

## 1. Project Overrides (Take Precedence Over lowRISC)

> **IMPORTANT — These rules differ from the lowRISC guide and must always be applied.**

1. **Port direction prefix** (mandatory): input `i_`, output `o_`, bidir `io_` — `i_data`, `o_valid`, `io_sda`.
   Suffixes (`_i`/`_o`/`_io`) are **forbidden** (lowRISC uses suffixes; this project does not).
   **Exception**: clock/reset ports take no prefix (`clk`, `sys_clk`, `rst_n`, `sys_rst_n`).
2. **Clock naming**: `clk` (single) or `{domain}_clk` (multi: `sys_clk`, `pixel_clk`) — never `clk_i`.
3. **Reset naming**: `rst_n` (single) or `{domain}_rst_n` (multi) — active-low async mandatory, never `rst_ni`.
4. **CamelCase fully prohibited** (lowRISC allows it for params/enums — this project does not):
   parameter `ALL_CAPS` (`DATA_WIDTH`), localparam `L_` prefix + `ALL_CAPS` (`L_ADDR_BITS`),
   enum values `ALL_CAPS` (`ST_IDLE`). All identifiers: `snake_case` or `ALL_CAPS` only.

## 2. Naming Conventions

| Target | Rule | Example |
|--------|------|---------|
| Module | `snake_case` | `axi_lite_slave` |
| Parameter (externally configurable) | `ALL_CAPS` | `DATA_WIDTH`, `DEPTH` |
| Local parameter (internal only) | `L_` prefix + `ALL_CAPS` | `L_ADDR_BITS`, `L_CNT_MAX` |
| Type (typedef) | `snake_case_t` suffix | `state_t`, `bus_req_t` |
| Enum type (typedef enum) | `snake_case_e` suffix | `state_e`, `cmd_type_e` |
| Enum values | `ALL_CAPS` | `ST_IDLE`, `WAIT_RESP` |
| `define macros | `ALL_CAPS` | `MAX_DEPTH`, `ASSERT_ON` |
| Instances | `u_` prefix | `u_fifo`, `u_arbiter` |
| Generate blocks | `gen_` prefix | `gen_pipeline_stage` |
| Signals (internal) | `snake_case` | `write_enable`, `addr_valid` |

> **UVM Exception**: UVM class member handles use `m_` prefix per industry convention
> (`m_driver`, `m_monitor`). `u_` prefix applies to RTL module instances only.

## 3. Filename Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Module | `module_name.sv` | `axi_lite_slave.sv` |
| Package | `module_name_pkg.sv` | `cabac_pkg.sv` |
| Interface | `module_name_if.sv` | `axi_if.sv` *(iverilog unsupported — do NOT generate, §5.3)* |
| Testbench | `tb_module_name.sv` | `tb_axi_lite_slave.sv` |
| SVA bind | `sva_module_name.sv` | `sva_axi_lite_slave.sv` |

**One module per file, filename matches module name.**

## 4. Language Rules (lint-enforced deltas)

- `logic` only (`reg`/`wire` forbidden); `always_ff` (sequential, `<=`) / `always_comb` (combinational, `=`); no `always_latch`
- ANSI ports (`input logic` / `output logic`); shared types via packages (`_pkg.sv`); use `typedef enum` / `typedef struct packed`
- `default` mandatory in all `case` statements (latch prevention); no combinational loops
- No `initial` blocks or `#delay` in synthesizable code; no magic numbers (use `parameter`/`localparam`)

## 5. Tool-Specific Caveats

### 5.1 Declaration Order — Xcelium Strict (IEEE 1800 §12.5)

> All identifiers must be declared before first use. Xcelium (xmvlog) strictly enforces
> sequential declaration visibility within a module; Verilator/iverilog are lenient.

Mandatory module structure order (see `templates/module-template.sv` for full scaffold):
```
1. parameter declarations          2. port declarations (ANSI)
3. import statements               4. typedef / localparam / enum
5. internal signal declarations    -- declaration boundary (no declarations below) --
6. assign statements               7. submodule instances (u_ prefix)
8. always_comb blocks              9. always_ff blocks
10. assertions (SVA)
```
Reordering concurrent statements has zero synthesis/simulation impact, but declarations
MUST always precede their first reference. Package file: `module_name_pkg.sv`.

### 5.2 VCS Strict `always_ff` Rules (Verification TB Caveat)

VCS enforces IEEE 1800 `always_ff` semantics strictly — a variable driven by `always_ff` must NOT also be driven by `initial`, `always_comb`, or `task` blocks (ICPD error). Verilator and iverilog are lenient on this.

**RTL code**: No issue — RTL should never mix `always_ff` with `initial` for the same signal.

**Verification TB code** (coverage counters, debug registers): If a testbench variable needs both sequential update (`posedge clk`) and procedural initialization (`initial` or `task`), use `always @(posedge clk)` instead of `always_ff`:
```systemverilog
// BAD — VCS ICPD error: cov_cnt driven by always_ff AND initial
always_ff @(posedge clk) cov_cnt <= cov_cnt + 1;
initial cov_cnt = 0;

// GOOD — always @(posedge) allows multiple drivers in TB
always @(posedge clk) cov_cnt <= cov_cnt + 1;
initial cov_cnt = 0;
```
This applies to **testbench only** — synthesizable RTL must always use `always_ff`.

**slang detection**: `slang -Weverything` catches this same `always_ff` multi-driver violation
at lint time (RTL mode). For TB files, use `slang --allow-dup-initial-drivers` to permit the
`initial` + `always_ff` pattern. The `run_lint.sh --tool slang` wrapper auto-detects RTL vs TB
based on file paths.

### 5.3 iverilog Incompatible Constructs (Do Not Generate in RTL)

> Applies to synthesizable RTL only. Verification TBs may use `interface` if the target simulator supports it.

- `interface` / `modport` and unpacked `struct` / `union` — unsupported by iverilog; use port lists / individual signals or `packed` versions
- `typedef struct packed` / `typedef union packed` are supported (OK to use)
- Do not modify existing or user-added code that contains these constructs

## 6. Design Style (Preferred)

### 6.1 Registered Outputs (Preferred)
Drive module outputs directly from a flip-flop. When a register/pipeline stage is needed, place it
at the **output** (compute → register → output port), NOT at the input followed by combinational
logic to the port. Registered outputs give the consumer a full clock period, keep the critical
path inside the module, and keep hierarchical STA/reuse clean. Combinational (unregistered)
outputs are acceptable for thin glue/passthrough logic, but must be a deliberate choice — not the
default place to put a needed flop.

### 6.2 Function / Task Purity (No Hidden External Dependencies)
`function`/`task` should operate **only on their arguments** (pure). Avoid reading module-level
signals not passed in — hidden inputs cause simulation-sensitivity surprises, obscure synthesis
intent, and hurt reuse. If an external (non-argument) dependency is genuinely unavoidable,
document it in a MANDATORY header comment at the top of the function/task:
`// External deps (read): cfg_mode, base_addr`

## 7. Storage Selection and SRAM Wrappers

### Storage Selection by Size
| Total Bits | Access Pattern | Implementation | Rationale |
|-----------|---------------|---------------|-----------|
| ≤256 | any | Flip-flop array (`logic [W-1:0] name [0:D-1]`) | SRAM overhead exceeds benefit |
| 257–4096 | 1 R/W | `sram_sp` wrapper | Area-efficient; register acceptable with rationale |
| 257–4096 | R+W simultaneous | `sram_tp` (single-clock) or `sram_dp` (dual-clock) | Separate read/write ports |
| >4096 | any | SRAM wrapper (mandatory) | Register file wastes area and power |
| any | >2 ports | Flip-flop array (register file) | Multi-port SRAM macros are rare in modern processes |

Wrapper code: `templates/sram_sp.sv`, `templates/sram_tp.sv`, `templates/sram_dp.sv` — copy into
`rtl/common/` if not already present. Parameters `DEPTH`/`WIDTH`; instances named `u_mem_{purpose}`;
synchronous read (1-cycle latency, matches real SRAM macro behavior). Register file (flip-flop
array) reads are combinational (0-cycle) — use only when downstream logic requires same-cycle data.

### Synthesis Behavior (translate_off blackbox + compiled macro)
The wrapper's behavioral array is guarded with `// synopsys translate_off … translate_on`, so
DC/Genus skip it at synthesis (simulators still run it) — the 2-D array is never elaborated into
flip-flops. A process define (e.g. `+define+RAT_MEM_TSMC_N22`, passed by `run_syn.sh
--mem-process`) activates a compiled-macro `` `ifdef `` branch instead. A real macro needs BOTH
`--mem-process` (activate branch) AND `--mem-lib <macro.db|.lib>` (resolve timing); missing either
→ the wrapper is blackboxed (`set_dont_touch` + `set_disable_timing`) with a WARNING.
Detail: `plugin_docs/specs/2026-05-26-synth-memory-blackbox-design.md`.

### Anti-Pattern: Combinational Read on Large Storage (DO NOT)
A >4096-bit register array read via `always_comb` mux (e.g., 4096×13-bit line buffer) produces
500K+ gate equivalents, 5h+ DC compile, and a 4096:1 mux per bit on the critical path.
Use an SRAM wrapper with synchronous read instead.

</Steps>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate SV code
(e.g., rtl-coder, sva-extractor). Agents should follow the conventions defined here.
</Tool_Usage>

<Examples>
Good/bad pattern pairs (naming, ports, declaration order): `examples/good-vs-bad.sv`.
</Examples>

<Escalation_And_Stop_Conditions>
- Convention violation found during rtl-lint-check → request fix from rtl-coder
- Different patterns needed for FPGA vs ASIC target → confirm target with user
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Port naming: `i_`/`o_`/`io_` prefix mandatory
- [ ] Clock: `clk` (single) or `{domain}_clk` (multi), Reset: `rst_n` or `{domain}_rst_n`
- [ ] No CamelCase: Parameter `ALL_CAPS`, localparam `L_` prefix, enum values `ALL_CAPS`
- [ ] Use `logic` only (no `reg`/`wire`)
- [ ] `always_ff` (sequential), `always_comb` (combinational)
- [ ] `default` present in all `case` statements
- [ ] Instance `u_` prefix, generate `gen_` prefix
- [ ] No magic numbers (use parameter/localparam)
- [ ] Filename = module name
- [ ] One module per file
- [ ] Declaration order: all `logic`/`typedef`/`localparam` before first `assign`/`always` (no forward references)
- [ ] Storage >256 bits uses `sram_sp`/`sram_tp`/`sram_dp` wrapper from `rtl/common/` (not inline array)
- [ ] TP (single-clock R+W) vs DP (dual-clock R+W) selected correctly per clock domain
- [ ] SRAM instances named `u_mem_{purpose}`
</Final_Checklist>
