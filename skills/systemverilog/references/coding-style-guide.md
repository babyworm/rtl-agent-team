# SystemVerilog RTL Design Guide

Comprehensive coding style, verification, and tool usage guide for RTL development.
Based on lowRISC SystemVerilog Coding Style with project-specific modifications.

---

## File Organization
- Use `.sv` extension for SystemVerilog files
- Use `.svh` for header files (included via preprocessor)
- One module per file, filename matches module name
- 100 characters max line length
- Use spaces (2 for indentation, 4 for continuation), never tabs
- POSIX line endings (`\n`)

---

## Naming Conventions

> **CamelCase is completely prohibited. All identifiers must use either `snake_case` or `ALL_CAPS`.**

| Construct | Style | Example |
|-----------|-------|---------|
| Modules, packages, interfaces | `lower_snake_case` | `axi_lite_slave` |
| Instance names | `u_<name>` prefix | `u_fifo`, `u_arbiter` |
| Signals (nets and ports) | `lower_snake_case` | `write_enable`, `addr_valid` |
| Parameters (externally tunable) | `ALL_CAPS` | `DATA_WIDTH`, `ADDR_WIDTH` |
| Local parameters (internal only) | `L_` prefix + `ALL_CAPS` | `L_ADDR_BITS`, `L_STATE_W` |
| Enumeration types (typedef) | `lower_snake_case_e` | `state_e`, `cmd_type_e` |
| Other typedefs | `lower_snake_case_t` | `bus_req_t`, `pixel_t` |
| Enumerated values | `ALL_CAPS` | `IDLE`, `WAIT_RESP`, `ST_DONE` |
| `define macros | `ALL_CAPS` | `MAX_DEPTH`, `ASSERT_ON` |
| Generate blocks | `gen_` prefix + `snake_case` | `gen_pipeline_stage` |

### CamelCase Prohibition Details

| lowRISC Original | Project Rule | Reason for Change |
|-----------------|--------------|-------------------|
| `parameter int unsigned Width = 8` | `parameter int unsigned WIDTH = 8` | CamelCase prohibited, unified to ALL_CAPS |
| `localparam int AddrBits = $clog2(Depth)` | `localparam int L_ADDR_BITS = $clog2(DEPTH)` | L_ prefix to distinguish external/internal |
| `StIdle`, `StProcess`, `StDone` | `ST_IDLE`, `ST_PROCESS`, `ST_DONE` | Enum values also ALL_CAPS |

### L_ Prefix Rules

```systemverilog
// Externally configurable parameter → ALL_CAPS, no L_
parameter int unsigned DATA_WIDTH = 32;
parameter int unsigned DEPTH      = 16;

// Internal-only localparam → L_ prefix
localparam int unsigned L_ADDR_W    = $clog2(DEPTH);
localparam int unsigned L_CNT_MAX   = DEPTH - 1;
localparam int unsigned L_DATA_BYTES = DATA_WIDTH / 8;
```

---

## Port Naming Convention

**MANDATORY**: Use direction PREFIXES on all port names (clock/reset excepted).

| Prefix | Meaning |
|--------|---------|
| `i_` | Input signal |
| `o_` | Output signal |
| `io_` | Bidirectional signal |
| *(none)* | Clock and reset ports only |

```systemverilog
module my_module (
  input  logic        clk,       // Clock: no i_ prefix
  input  logic        rst_n,     // Reset: no i_ prefix
  input  logic [7:0]  i_data,
  output logic        o_valid,
  inout  wire  [3:0]  io_bus
);
```

**NEVER use suffixes** (`_i`, `_o`, `_io`).
**Exception**: Clock (`clk`, `sys_clk`) and reset (`rst_n`, `sys_rst_n`) ports do NOT need `i_` prefix.

---

## Reset Convention (ALWAYS)

**Active-low asynchronous reset**:
- Signal name: `rst_n` (single domain) or `sys_rst_n` (multi-domain)
- Triggered on negative edge: `negedge rst_n`

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    state_q <= ST_IDLE;
    count_q <= '0;
  end else begin
    state_q <= state_d;
    count_q <= count_d;
  end
end
```

---

## Signal Suffixes

| Suffix | Meaning |
|--------|---------|
| `_n` | Active low signal |
| `_d` | Combinational (next state) input to register |
| `_q` | Registered output |
| `_q2`, `_q3` | Pipeline stages (2, 3 cycles delay) |

---

## Module Structure Template

```systemverilog
// Copyright notice
// SPDX-License-Identifier: Apache-2.0
//
// Brief module description

module module_name #(
  parameter int unsigned DATA_WIDTH = 8,
  parameter int unsigned DEPTH      = 16
) (
  input  logic                      clk,
  input  logic                      rst_n,

  // Interface group 1
  input  logic [DATA_WIDTH-1:0]     i_data,
  input  logic                      i_valid,
  output logic                      o_ready,

  // Interface group 2
  output logic [DATA_WIDTH-1:0]     o_result,
  output logic                      o_done
);

  // Local parameters
  localparam int unsigned L_ADDR_W = $clog2(DEPTH);

  // Type definitions
  typedef enum logic [1:0] {
    ST_IDLE,
    ST_PROCESS,
    ST_DONE
  } state_e;

  // Signal declarations
  state_e state_q, state_d;
  logic [DATA_WIDTH-1:0] data_q, data_d;

  // Submodule instantiations
  submodule u_submodule (
    .clk,
    .rst_n,
    .i_data   (data_q),
    .o_result (result_internal)
  );

  // Combinational logic
  always_comb begin
    state_d = state_q;
    data_d  = data_q;

    unique case (state_q)
      ST_IDLE: begin
        if (i_valid) begin
          state_d  = ST_PROCESS;
          data_d   = i_data;
        end
      end
      ST_PROCESS: begin
        state_d = ST_DONE;
      end
      ST_DONE: begin
        state_d = ST_IDLE;
      end
      default: state_d = ST_IDLE;
    endcase
  end

  // Sequential logic (active-low async reset)
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q <= ST_IDLE;
      data_q  <= '0;
    end else begin
      state_q <= state_d;
      data_q  <= data_d;
    end
  end

  // Output assignments
  assign o_ready  = (state_q == ST_IDLE);
  assign o_done   = (state_q == ST_DONE);
  assign o_result = data_q;

endmodule
```

---

## Synthesizable Constructs

### Use These:
- `logic` for all signals (not `reg` or `wire` except for tri-state)
- `always_comb` for combinational logic
- `always_ff` for sequential logic
- `always_latch` only when latches are intended (rare)
- Explicit bit widths: `8'd255` not `255`
- `unique case` or `priority case` for full/parallel case
- Blocking (`=`) in `always_comb`, non-blocking (`<=`) in `always_ff`

### Avoid These:
- `initial` blocks in synthesizable code
- `#` delays in RTL
- System tasks (`$display`, etc.) in RTL (OK in testbench)
- `force`/`release`
- Implicit nets
- CamelCase in any identifier

---

## Width Matching
- Always explicit widths for literals: `4'b0001`, `8'hFF`
- Port connections must match widths exactly
- Use `$clog2()` for address width calculations

---

## CDC Design Rules

| Rule | Description |
|------|-------------|
| **Single-bit sync** | Always use 2+ stage synchronizer |
| **Multi-bit data** | Use Gray code, async FIFO, or handshake |
| **No glitch** | Ensure source signal is stable for 2+ dest clk cycles |
| **Reset sync** | Async assert, sync deassert in each domain |
| **Control before data** | Sync control signals, data follows safely |

---

## Verification Workflow

```
1. lsp_diagnostics     - Real-time lint during editing
2. verilator --lint    - Comprehensive lint check
3. Simulation:
   - Verilator         - Fast, cycle-accurate (default)
   - Icarus Verilog    - When timing/X/Z needed
   - cocotb            - Python testbenches (optional)
4. yosys synth         - Synthesis check (optional)
```

---

## Anti-Patterns (NEVER DO)

| Category | Forbidden |
|----------|-----------|
| Naming | CamelCase in any identifier |
| Naming | Parameter with UpperCamelCase (use ALL_CAPS) |
| Naming | Enum value with UpperCamelCase (use ALL_CAPS) |
| Reset | Synchronous reset, active-high reset, missing reset |
| Timing | Combinational loops, multi-cycle paths without constraints |
| Style | Mixed blocking/non-blocking in same block, implicit widths |
| Signals | Undriven outputs, unused inputs without purpose |
| Verification | Module without testbench, untested edge cases |
| Lint | Ignoring Verilator warnings without justification |
| CDC | Direct multi-bit signal crossing without sync |
| CDC | Single-flop synchronizer, missing reset sync |

---

## Work Principles

1. **RTL First**: Write synthesizable RTL, then create testbench
2. **Verify Everything**: Never consider a module complete without passing tests
3. **Lint Clean**: All code must pass `verilator --lint-only -Wall`
4. **No CamelCase**: All identifiers are snake_case or ALL_CAPS
5. **Parameterize**: Use parameters for configurable modules, L_ prefix for internal
6. **Reset Properly**: Always active-low async reset, proper reset values
7. **Match Patterns**: Follow existing codebase conventions
8. **CDC Safety**: Always use proper synchronization for clock crossings
