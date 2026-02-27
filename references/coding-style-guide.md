# SystemVerilog Coding Style Guide — Detailed Reference

> This document is the detailed reference for the `systemverilog` skill.
> For core rules, see `<Steps>` in `skills/systemverilog/SKILL.md`.

## 1. Naming Convention Details

### 1.1 Identifier Rules Summary Table

| Target | Style | Prefix/Suffix | Example | Forbidden |
|--------|-------|---------------|---------|-----------|
| Module | `snake_case` | — | `axi_lite_slave` | `AXI_Lite_Slave` |
| Interface | `snake_case` | `_if` suffix | `axi_if` | `AXI_IF` |
| Package | `snake_case` | `_pkg` suffix | `cabac_pkg` | `CabacPkg` |
| Parameter (external) | `ALL_CAPS` | — | `DATA_WIDTH` | `DataWidth` |
| Localparam (internal) | `ALL_CAPS` | `L_` prefix | `L_ADDR_BITS` | `AddrBits` |
| Typedef struct | `snake_case` | `_t` suffix | `bus_req_t` | `BusReq` |
| Typedef enum type | `snake_case` | `_e` suffix | `state_e` | `StateType` |
| Enum value | `ALL_CAPS` | — | `ST_IDLE` | `StIdle` |
| `define macro | `ALL_CAPS` | — | `MAX_DEPTH` | `maxDepth` |
| Instance | `snake_case` | `u_` prefix | `u_fifo` | `fifo_inst` |
| Generate block | `snake_case` | `gen_` prefix | `gen_pipeline` | `GEN_PIPE` |
| Internal signal | `snake_case` | — | `write_en` | `writeEn` |
| Input port | `snake_case` | `i_` prefix | `i_data` | `data_i` |
| Output port | `snake_case` | `o_` prefix | `o_valid` | `valid_o` |
| Bidirectional port | `snake_case` | `io_` prefix | `io_sda` | `sda_io` |
| Clock | `snake_case` | — | `sys_clk`, `clk` | `clk_i` |
| Reset | `snake_case` | `_n` suffix | `sys_rst_n`, `rst_n` | `rst_ni` |

### 1.2 Clock/Reset Exception Rules

Clock and reset ports do **not** use the `i_` prefix:
```systemverilog
// CORRECT
input logic sys_clk,
input logic sys_rst_n,
input logic pixel_clk,
input logic pixel_rst_n,

// ALSO CORRECT (single domain)
input logic clk,
input logic rst_n,

// WRONG
input logic i_sys_clk,    // i_ prefix on clock
input logic i_sys_rst_n,  // i_ prefix on reset
input logic clk_i,        // suffix style
input logic rst_ni,       // suffix style
```

### 1.3 Pipeline Stage Signals

| Pattern | Usage | Example |
|---------|-------|---------|
| `{name}_d` | combinational (next value) | `state_d`, `count_d` |
| `{name}_q` | registered (current value) | `state_q`, `count_q` |
| `stage{N}_{name}` | pipeline register | `stage1_data`, `stage2_valid` |

## 2. Type Usage Rules

### 2.1 Required Types

```systemverilog
// Always use logic
logic [7:0] data;          // NOT: reg [7:0] data; wire [7:0] data;
logic       valid;

// Explicit signed for signed arithmetic
logic signed [15:0] coefficient;

// Use int unsigned for parameters with bit width
parameter int unsigned DATA_WIDTH = 32;
parameter int unsigned DEPTH      = 16;
```

### 2.2 Struct/Enum Patterns

```systemverilog
// Define in package
package my_module_pkg;
  typedef struct packed {
    logic [31:0] addr;
    logic [31:0] data;
    logic        write;
  } bus_req_t;

  typedef enum logic [2:0] {
    ST_IDLE    = 3'b000,
    ST_SETUP   = 3'b001,
    ST_ACCESS  = 3'b010,
    ST_DONE    = 3'b011
  } state_e;
endpackage
```

### 2.3 Forbidden Patterns

```systemverilog
// FORBIDDEN
reg  [7:0] data;           // reg keyword
wire [7:0] result;         // wire keyword
integer    count;          // use int unsigned
real       delay_val;      // no real in synth code
```

## 3. Module Structure Standard Order

```systemverilog
module my_module
  import my_module_pkg::*;
#(
  // 1. Parameters (ALL_CAPS)
  parameter int unsigned DATA_WIDTH = 32,
  parameter int unsigned DEPTH      = 16
) (
  // 2. Clock/Reset (no i_ prefix)
  input  logic                    sys_clk,
  input  logic                    sys_rst_n,

  // 3. Input ports (i_ prefix, grouped by interface)
  input  logic [DATA_WIDTH-1:0]  i_data,
  input  logic                    i_valid,

  // 4. Output ports (o_ prefix)
  output logic [DATA_WIDTH-1:0]  o_result,
  output logic                    o_ready
);

  // 5. Localparams (L_ prefix)
  localparam int unsigned L_ADDR_BITS = $clog2(DEPTH);

  // 6. Type definitions (if not in _pkg)
  typedef enum logic [1:0] { ST_IDLE, ST_RUN, ST_DONE } state_e;

  // 7. Internal signals
  state_e state_q, state_d;
  logic [DATA_WIDTH-1:0] data_q;

  // 8. Submodule instances (u_ prefix)
  my_sub_module u_sub (
    .sys_clk   (sys_clk),
    .sys_rst_n (sys_rst_n),
    .i_data    (data_q),
    .o_result  (o_result)
  );

  // 9. Combinational logic (always_comb)
  always_comb begin
    state_d = state_q;
    // ...
  end

  // 10. Sequential logic (always_ff)
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) begin
      state_q <= ST_IDLE;
      data_q  <= '0;
    end else begin
      state_q <= state_d;
      data_q  <= i_data;
    end
  end

  // 11. Assertions (inline or reference bind file)
  // See sva_{module}.sv for formal assertions

endmodule
```

## 4. always Block Rules

| Block | Usage | Assignment | sensitivity |
|-------|-------|------------|-------------|
| `always_ff` | Sequential | `<=` (non-blocking) | `@(posedge clk or negedge rst_n)` |
| `always_comb` | Combinational | `=` (blocking) | Automatic |
| `always_latch` | **Forbidden** | — | — |
| `always @(*)` | **Forbidden** | — | Use `always_comb` |

## 5. case Statement Rules

```systemverilog
// REQUIRED: default for every case
always_comb begin
  unique case (state_q)
    ST_IDLE:  state_d = i_valid ? ST_RUN : ST_IDLE;
    ST_RUN:   state_d = done   ? ST_DONE : ST_RUN;
    ST_DONE:  state_d = ST_IDLE;
    default:  state_d = ST_IDLE;  // REQUIRED
  endcase
end
```

- `unique case`: Guarantees all values are covered (synthesis optimization hint)
- `priority case`: When priority encoding is needed
- plain `case`: When no special semantics needed (default is still required)

## 6. Port Declaration Style

```systemverilog
// ANSI style (REQUIRED)
module my_module #(
  parameter int unsigned WIDTH = 8
) (
  input  logic              sys_clk,
  input  logic              sys_rst_n,
  input  logic [WIDTH-1:0]  i_data,
  output logic [WIDTH-1:0]  o_data
);

// NON-ANSI style (FORBIDDEN)
module my_module(sys_clk, sys_rst_n, i_data, o_data);
  input sys_clk;     // WRONG
  input [7:0] i_data; // WRONG
```
