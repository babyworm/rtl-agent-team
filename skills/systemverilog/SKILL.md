---
name: systemverilog
description: "SystemVerilog coding convention and design guideline skill. Enforces lowRISC style + project overrides for all .sv/.v file generation. Covers naming, module structure, power optimization, FPGA considerations, and pipelining for timing closure."
user-invocable: false
---

<Purpose>
SystemVerilog coding standards and design guidelines.
All agents generating or modifying .sv, .v files must follow the rules in this skill.

Target standard: **IEEE 1800-2009** for synthesizable RTL.
- 2009 features: always_ff, always_comb, logic, typedef enum/struct, packages — all available
- `interface`/`modport` is 2009 standard but iverilog unsupported — do NOT generate in RTL (see §4.3)
- 2012+ features (checker, interface class, let, soft constraint) are verification-only — do NOT use in RTL
- Tool flags: iverilog uses `-g2012` for parser compatibility (2012 parser handles 2009 code)

Baseline: lowRISC SystemVerilog Coding Style Guide (https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md)
Project overrides take precedence over default lowRISC rules.
</Purpose>

<Use_When>
- When writing or modifying .sv, .svh, .v, .vh files
- During Phase 4 (RTL implementation) work
- During Phase 5 (Verification) when writing SVA or SV testbenches
- When preparing code before running rtl-lint-check or rtl-synth-check skills
- Agents: rtl-coder, sva-extractor, testbench-dev, lint-checker
</Use_When>

<Do_Not_Use_When>
- When writing SystemC/C++ code → use `systemc` skill
- When writing Python cocotb tests → refer to cocotb rules in `rtl-p5s-func-verify` skill
- When only writing documentation
</Do_Not_Use_When>

<Why_This_Exists>
Consistent coding standards ensure lint pass rate, synthesis quality, and team readability all at once.
Although based on lowRISC, this project has its own overrides for port naming, clock/reset rules, etc.,
so they are managed as a separate skill to ensure all SV-generating agents reference the same rules.
</Why_This_Exists>

<Execution_Policy>
- The rules in this skill apply to all agents that generate SV code
- Violations will result in a FAIL verdict from the rtl-lint-check skill
- Use `templates/module-template.sv` as the starting point for new modules
- Review `examples/good-vs-bad.sv` for correct/incorrect pattern examples
- See `references/coding-style-guide.md` for detailed project overrides vs. original lowRISC rules
</Execution_Policy>

<Steps>

## 1. Project Overrides (Take Precedence Over lowRISC)

> **IMPORTANT — The following 3 rules differ from the lowRISC guide and must always be applied.**

### 1.1 Port Direction Prefix (Mandatory, Clock/Reset Excepted)
- Input: `i_`, Output: `o_`, Bidirectional: `io_` — **mandatory**
- Example: `i_data`, `o_valid`, `io_sda` (NOT `data_i`, `valid_o`)
- **Exception**: Clock and reset ports do not need the `i_` prefix (`clk`, `sys_clk`, `rst_n`, `sys_rst_n`)
- Using suffixes (`_i`, `_o`, `_io`) is **forbidden**
- lowRISC uses suffixes, but this project **requires prefixes (clock/reset excepted)**

### 1.2 Clock Naming
- Single clock: `clk` (default) or `{domain}_clk` (multi-clock)
- Multi-clock domains: `sys_clk`, `pixel_clk`, `axi_clk`
- NOT `clk_i`, NOT suffix

### 1.3 Reset Naming
- Single reset: `rst_n` (default) or `{domain}_rst_n` (multi-domain)
- Active-low asynchronous reset is mandatory
- Example: `rst_n`, `sys_rst_n`, `pixel_rst_n` (NOT `rst_ni`)

### 1.4 CamelCase Prohibition (Additional Override)
- lowRISC uses `UpperCamelCase` for Parameters and Enum values
- **This project prohibits CamelCase entirely**
- Parameter: `ALL_CAPS` (`DATA_WIDTH`, NOT `DataWidth`)
- Localparam (internal): `L_` prefix + `ALL_CAPS` (`L_ADDR_BITS`, NOT `AddrBits`)
- Enum values: `ALL_CAPS` (`ST_IDLE`, NOT `StIdle`)

## 2. Naming Conventions

> **IMPORTANT — CamelCase is completely prohibited. All identifiers must use only `snake_case` or `ALL_CAPS`.**
> Detailed rules: see `references/coding-style-guide.md`.

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

### CamelCase Prohibition Examples

| Forbidden (CamelCase) | Correct Form |
|-----------------------|-------------|
| `parameter int Width = 8` | `parameter int unsigned WIDTH = 8` |
| `localparam AddrBits = $clog2(Depth)` | `localparam L_ADDR_BITS = $clog2(DEPTH)` |
| `StIdle`, `StProcess` | `ST_IDLE`, `ST_PROCESS` |
| Any `UpperCamelCase` | `ALL_CAPS` or `snake_case` |

## 3. Filename Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Module | `module_name.sv` | `axi_lite_slave.sv` |
| Package | `module_name_pkg.sv` | `cabac_pkg.sv` |
| Interface | `module_name_if.sv` | `axi_if.sv` *(iverilog unsupported — do NOT generate, §4.3)* |
| Testbench | `tb_module_name.sv` | `tb_axi_lite_slave.sv` |
| SVA bind | `sva_module_name.sv` | `sva_axi_lite_slave.sv` |

**One module per file, filename matches module name.**

## 4. SystemVerilog Coding Rules

### 4.1 Mandatory Usage
- Use `logic` (using `reg`/`wire` is forbidden)
- `always_ff` for sequential (non-blocking `<=`)
- `always_comb` for combinational (blocking `=`)
- Actively use `typedef enum` / `typedef struct packed`
- Define shared types via packages (`_pkg.sv`)
- Ports: `input logic` / `output logic` (ANSI style)
- No magic numbers — use `parameter` or `localparam`

### 4.2 Prohibited Practices
- Using `reg`, `wire` keywords is forbidden
- Using `always_latch` is forbidden (except for explicit latches; generally prohibited)
- `initial` blocks in synthesizable code are forbidden
- Latch prevention: `default` is mandatory in all `case` statements
- Combinational loops are forbidden
- `#delay` in synthesizable code is forbidden
- Forward references are forbidden: all signals, types, and parameters must be declared before first use (IEEE 1800 §12.5). Xcelium (xmvlog) strictly enforces sequential declaration visibility within a module

### 4.3 VCS Strict `always_ff` Rules (Verification TB Caveat)

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

### 4.4 iverilog Incompatible Constructs (Do Not Generate)

> This restriction applies to synthesizable RTL code only. Verification TBs may use `interface` if the target simulator supports it.

- `interface` / `modport` — unsupported by iverilog. Use port lists instead
- unpacked `struct` / `union` — unsupported by iverilog. Use individual signals or `packed` versions
- Agents must NOT generate these constructs in RTL code
- `typedef struct packed` / `typedef union packed` are supported (OK to use)
- Do not modify existing code or user-added code that contains these constructs

### 4.5 Module Structure (Mandatory Declaration Order)

> **IMPORTANT — IEEE 1800 §12.5 requires identifiers to be declared before first use.**
> Xcelium (xmvlog) strictly enforces sequential declaration visibility.
> Reordering concurrent statements (assign, always_ff, always_comb) has zero synthesis/simulation impact,
> but declarations MUST always precede their first reference.

```
module_name_pkg.sv    <- Shared type/constant definitions
module_name.sv        <- Module implementation (order is MANDATORY):
  1. parameter declarations
  2. port declarations (ANSI style)
  3. import statements
  4. typedef / localparam / enum       <- all types and constants
  5. internal signal declarations      <- all signals before any logic
  -- declaration boundary ------------ (no declarations below this line)
  6. assign statements                 <- continuous assignments
  7. submodule instances (u_ prefix)
  8. always_comb blocks                <- combinational logic
  9. always_ff blocks                  <- sequential logic
  10. assertions (SVA)
```
See `templates/module-template.sv` for complete scaffold.

## 5. Context-Specific Optimizations (Summary)

> The items below apply only when specific optimizations are needed. See the `<Advanced>` section for detailed patterns and code examples.

- **Power Optimization**: Clock gating (ICG), operand isolation, power domains → `<Advanced>` section A.1
- **Memory Wrapper Patterns**: Storage selection, SRAM wrappers (SP/DP/TDP), foundry replacement → `<Advanced>` section A.2
- **FPGA Considerations**: BRAM/DSP inference, XDC constraints, ILA debugging, IP Core → `<Advanced>` section A.3
- **Pipelining for Timing Closure**: Pipeline insertion criteria, retiming, valid/ready pipelining → `<Advanced>` section A.4

</Steps>

<Advanced>

## A.1 Power Optimization

### Clock Gating
- Gate the clock for inactive blocks to reduce dynamic power
- Use of ICG (Integrated Clock Gating) cells is recommended
```systemverilog
// Clock gating pattern
logic clk_enable;
logic gated_clk;

// Use dedicated ICG cell (synthesis tool maps to library cell)
assign gated_clk = sys_clk & clk_enable;  // For simulation only
// Synthesis: replace with ICG instantiation or let tool infer
```

### Power-Aware Coding Patterns
- Minimize unnecessary toggling: check enable before mux output
- Memory read enable: only read SRAM when needed
- Operand isolation: mask operator inputs to zero
```systemverilog
// Operand isolation — prevent unnecessary switching in multiplier
logic [15:0] mul_a_gated, mul_b_gated;
assign mul_a_gated = i_mul_valid ? i_mul_a : '0;
assign mul_b_gated = i_mul_valid ? i_mul_b : '0;
assign mul_result  = mul_a_gated * mul_b_gated;
```

### Power Domain Considerations
- Explicitly specify level shifter placement for multi-voltage domains
- Mark retention registers with comments when needed

## A.2 Memory Wrapper Patterns

### Storage Selection by Size
| Total Bits | Ports | Implementation | Rationale |
|-----------|-------|---------------|-----------|
| ≤256 | any | Flip-flop array (`logic [W-1:0] name [0:D-1]`) | SRAM overhead exceeds benefit |
| 257–4096, ≤2 R/W | ≤2 | `sram_sp` / `sram_dp` wrapper | Area-efficient; register acceptable with rationale |
| >4096, ≤2 R/W | ≤2 | `sram_sp` / `sram_dp` wrapper (mandatory) | Register file wastes area and power |
| any, >2 R/W | >2 | Flip-flop array (register file) | Multi-port SRAM macros are rare |

### Standard SRAM Wrapper — Single-Port (SP)
Place in `rtl/common/sram_sp.sv`. Instance with `u_mem_` prefix.
```systemverilog
module sram_sp #(
  parameter int DEPTH = 256,
  parameter int WIDTH = 32
) (
  input  logic                    clk,
  input  logic                    i_ce,
  input  logic                    i_we,
  input  logic [$clog2(DEPTH)-1:0] i_addr,
  input  logic [WIDTH-1:0]        i_wdata,
  output logic [WIDTH-1:0]        o_rdata
);

  localparam int L_ADDR_W = $clog2(DEPTH);

  logic [WIDTH-1:0] mem [0:DEPTH-1];

  always_ff @(posedge clk) begin
    if (i_ce) begin
      if (i_we) begin
        mem[i_addr] <= i_wdata;
      end
      o_rdata <= mem[i_addr];  // 1-cycle read latency
    end
  end

endmodule
```

### Standard SRAM Wrapper — Simple Dual-Port (DP)
Place in `rtl/common/sram_dp.sv`. Port A = write, Port B = read.
```systemverilog
module sram_dp #(
  parameter int DEPTH = 256,
  parameter int WIDTH = 32
) (
  input  logic                    clk,
  // Port A — write
  input  logic                    i_we,
  input  logic [$clog2(DEPTH)-1:0] i_waddr,
  input  logic [WIDTH-1:0]        i_wdata,
  // Port B — read
  input  logic                    i_re,
  input  logic [$clog2(DEPTH)-1:0] i_raddr,
  output logic [WIDTH-1:0]        o_rdata
);

  logic [WIDTH-1:0] mem [0:DEPTH-1];

  always_ff @(posedge clk) begin
    if (i_we) begin
      mem[i_waddr] <= i_wdata;
    end
    if (i_re) begin
      o_rdata <= mem[i_raddr];  // 1-cycle read latency
    end
  end

endmodule
```

### Standard SRAM Wrapper — True Dual-Port (TDP)
Place in `rtl/common/sram_tdp.sv`. Both ports can read and write.
```systemverilog
module sram_tdp #(
  parameter int DEPTH = 256,
  parameter int WIDTH = 32
) (
  input  logic                    clk,
  // Port A
  input  logic                    i_ce_a,
  input  logic                    i_we_a,
  input  logic [$clog2(DEPTH)-1:0] i_addr_a,
  input  logic [WIDTH-1:0]        i_wdata_a,
  output logic [WIDTH-1:0]        o_rdata_a,
  // Port B
  input  logic                    i_ce_b,
  input  logic                    i_we_b,
  input  logic [$clog2(DEPTH)-1:0] i_addr_b,
  input  logic [WIDTH-1:0]        i_wdata_b,
  output logic [WIDTH-1:0]        o_rdata_b
);

  logic [WIDTH-1:0] mem [0:DEPTH-1];

  // Single always_ff to avoid multi-driver on mem (slang -Weverything).
  // WARNING: Same-address write collision (i_we_a && i_we_b && i_addr_a == i_addr_b)
  // is UNDEFINED in real SRAM macros. This behavioral model lets port B win silently.
  // Designs must prevent same-address simultaneous writes at the protocol level.
  always_ff @(posedge clk) begin
    if (i_ce_a) begin
      if (i_we_a) mem[i_addr_a] <= i_wdata_a;
      o_rdata_a <= mem[i_addr_a];
    end
    if (i_ce_b) begin
      if (i_we_b) mem[i_addr_b] <= i_wdata_b;
      o_rdata_b <= mem[i_addr_b];
    end
  end

endmodule
```

### Foundry Macro Replacement
- Behavioral wrappers are used for simulation and FPGA synthesis (infers BRAM)
- For ASIC: replace wrapper body with foundry macro behind `` `ifdef SYNTHESIS `` guard
- Wrapper interface stays identical — no changes to instantiating modules
- DEPTH/WIDTH parameters must match foundry macro configuration

## A.3 FPGA Considerations

### Resource Inference Guide
| Resource | Inference Pattern | Notes |
|----------|-------------------|-------|
| BRAM | `logic [W-1:0] mem [0:D-1]` + sync read | Async read infers distributed RAM |
| DSP | `a * b + c` pattern | Better inference with pipeline registers |
| SRL | shift register (`always_ff` chain) | Auto-inferred, no explicit control needed |

### XDC Constraints (Xilinx)
- Similar to SDC but includes Xilinx-specific commands
- `create_clock`, `set_input_delay`, `set_output_delay` are identical
- FPGA-specific: `set_property IOSTANDARD`, `set_property LOC`

### ILA Debugging
- Apply `(* mark_debug = "true" *)` attribute to signals targeted for debug
- Insert ILA core after synthesis for real-time waveform inspection

### IP Core Usage
- Xilinx: AXI Interconnect, MIG (DDR controller), AXI DMA
- Intel: Platform Designer (Qsys) IP
- IP instances also follow the `u_` prefix convention

## A.4 Pipelining for Timing Closure

### Pipeline Insertion Criteria
- When timing reports show critical path violations
- When combinational depth exceeds the allowable range for target frequency
- When logic depth warnings are generated by the `rtl-synth-check` skill

### Pipeline Patterns
```systemverilog
// Before: long combinational path
assign o_result = func_a(func_b(func_c(i_data)));

// After: 2-stage pipeline
logic [W-1:0] stage1_q;
always_ff @(posedge sys_clk or negedge sys_rst_n) begin
  if (!sys_rst_n) stage1_q <= '0;
  else            stage1_q <= func_c(i_data);
end
assign o_result = func_a(func_b(stage1_q));
```

### Register Retiming
- Leverage the synthesis tool's retiming option (DC: `compile_ultra -retime`, Genus: `syn_opt -retiming`)
- Do not apply `dont_touch` to registers targeted for retiming

### Valid/Ready Pipeline
- When inserting pipeline stages, pipeline the handshake signals as well
- Backpressure propagation: `o_ready` propagates backward from the next stage's `i_ready`

</Advanced>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate SV code
(e.g., rtl-coder, sva-extractor). Agents should follow the conventions defined here.
</Tool_Usage>

<Examples>
<Good>
Follows project rules: ALL_CAPS parameter, L_ prefix localparam, snake_case, no CamelCase.
```systemverilog
module cabac_encoder #(
  parameter int unsigned CTX_ADDR_W = 9
) (
  input  logic                   clk,
  input  logic                   rst_n,
  input  logic [CTX_ADDR_W-1:0]  ctx_addr,
  output logic                   bin_valid
);
  localparam int unsigned L_CTX_DEPTH = 2 ** CTX_ADDR_W;

  typedef enum logic [1:0] {
    ST_IDLE,
    ST_ENCODE,
    ST_DONE
  } state_e;
```
</Good>
<Bad>
CamelCase, suffix, reg/wire, magic numbers:
```systemverilog
module cabac_encoder #(
  parameter int CtxAddrWidth = 9   // WRONG: CamelCase
) (
  input  wire        clk_i,        // WRONG: suffix, wire
  input  reg         rst_ni,       // WRONG: reg, suffix
  input  [8:0]       ctx_addr_i,   // WRONG: suffix, magic width
  output             bin_valid_o   // WRONG: no type, suffix
);
  localparam AddrBits = 4;         // WRONG: CamelCase, no L_ prefix
  typedef enum logic [1:0] {
    StIdle, StEncode, StDone       // WRONG: CamelCase enum values
  } state_e;
```
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Convention violation found during rtl-lint-check → request fix from rtl-coder
- Power optimization pattern affects functionality → request review from rtl-architect
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
- [ ] Storage >256 bits with ≤2 ports uses `sram_sp`/`sram_dp` wrapper from `rtl/common/` (not inline array)
- [ ] SRAM instances named `u_mem_{purpose}`
</Final_Checklist>
