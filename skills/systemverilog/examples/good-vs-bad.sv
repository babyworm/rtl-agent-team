// =============================================================================
// SystemVerilog Coding Convention: Good vs Bad Examples
// =============================================================================

// ============================================================
// EXAMPLE 1: Port Naming
// ============================================================

// BAD — lowRISC suffix style (NOT used in this project)
module bad_port_naming (
  input  wire        clk_i,          // WRONG: wire, suffix
  input  wire        rst_ni,         // WRONG: wire, suffix
  input  wire [7:0]  data_i,         // WRONG: wire, suffix
  output reg  [7:0]  data_o          // WRONG: reg, suffix
);
endmodule

// GOOD — project prefix style
module good_port_naming (
  input  logic       sys_clk,        // OK: domain_clk
  input  logic       sys_rst_n,      // OK: domain_rst_n (active-low)
  input  logic [7:0] i_data,         // OK: i_ prefix
  output logic [7:0] o_data          // OK: o_ prefix
);
endmodule


// ============================================================
// EXAMPLE 2: Sequential vs Combinational
// ============================================================

// BAD — using 'always' (Verilog-2001 style)
module bad_always (
  input  logic       sys_clk,
  input  logic       sys_rst_n,
  input  logic [7:0] i_data,
  output logic [7:0] o_data
);
  // WRONG: plain 'always' doesn't distinguish ff/comb
  always @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n)
      o_data <= '0;
    else
      o_data <= i_data;
  end
endmodule

// GOOD — explicit always_ff / always_comb
module good_always (
  input  logic       sys_clk,
  input  logic       sys_rst_n,
  input  logic [7:0] i_data,
  output logic [7:0] o_data
);
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n)
      o_data <= '0;        // non-blocking for sequential
    else
      o_data <= i_data;
  end
endmodule


// ============================================================
// EXAMPLE 3: Latch Prevention
// ============================================================

// BAD — missing default in case, causes latch inference
module bad_case_latch (
  input  logic [1:0] i_sel,
  input  logic [7:0] i_a, i_b,
  output logic [7:0] o_result
);
  always_comb begin
    case (i_sel)
      2'b00: o_result = i_a;
      2'b01: o_result = i_b;
      // WRONG: missing 2'b10, 2'b11, and no default → LATCH!
    endcase
  end
endmodule

// GOOD — default prevents latch
module good_case_no_latch (
  input  logic [1:0] i_sel,
  input  logic [7:0] i_a, i_b,
  output logic [7:0] o_result
);
  always_comb begin
    unique case (i_sel)
      2'b00:   o_result = i_a;
      2'b01:   o_result = i_b;
      default: o_result = '0;  // prevents latch
    endcase
  end
endmodule


// ============================================================
// EXAMPLE 4: Parameter Usage (No Magic Numbers)
// ============================================================

// BAD — magic numbers everywhere
module bad_magic_numbers (
  input  logic        sys_clk,
  input  logic        sys_rst_n,
  input  logic [7:0]  i_data,
  output logic [15:0] o_result
);
  logic [7:0] mem [0:255];  // magic: 8, 256
  logic [3:0] count;        // magic: 4

  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) count <= 4'd0;
    else if (count < 4'd10) count <= count + 4'd1;  // magic: 10
  end
endmodule

// GOOD — parameterized
module good_parameterized #(
  parameter int unsigned DATA_WIDTH  = 8,
  parameter int unsigned MEM_DEPTH   = 256,
  parameter int unsigned MAX_COUNT   = 10
) (
  input  logic                      sys_clk,
  input  logic                      sys_rst_n,
  input  logic [DATA_WIDTH-1:0]     i_data,
  output logic [2*DATA_WIDTH-1:0]   o_result
);
  localparam int unsigned L_ADDR_WIDTH  = $clog2(MEM_DEPTH);
  localparam int unsigned L_COUNT_WIDTH = $clog2(MAX_COUNT + 1);

  logic [DATA_WIDTH-1:0] mem [0:MEM_DEPTH-1];
  logic [L_COUNT_WIDTH-1:0] count;

  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) count <= '0;
    else if (count < L_COUNT_WIDTH'(MAX_COUNT)) count <= count + 1'b1;
  end
endmodule


// ============================================================
// EXAMPLE 5: Instance & Generate Naming
// ============================================================

// BAD — no prefix
module bad_instance_naming (
  input logic sys_clk, sys_rst_n
);
  my_fifo fifo_inst (.*);           // WRONG: no u_ prefix
  for (genvar i = 0; i < 4; i++) begin : stage  // WRONG: no gen_ prefix
    pipeline_reg pr (.*);           // WRONG: no u_ prefix
  end
endmodule

// GOOD — u_ and gen_ prefixes
module good_instance_naming (
  input logic sys_clk, sys_rst_n
);
  my_fifo u_fifo (.*);             // OK: u_ prefix
  for (genvar i = 0; i < 4; i++) begin : gen_stage  // OK: gen_ prefix
    pipeline_reg u_pipe_reg (.*);  // OK: u_ prefix
  end
endmodule


// ============================================================
// EXAMPLE 6: Power Optimization — Operand Isolation
// ============================================================

// BAD — multiplier toggles even when result is unused
module bad_power (
  input  logic        sys_clk, sys_rst_n,
  input  logic        i_valid,
  input  logic [15:0] i_a, i_b,
  output logic [31:0] o_result
);
  // Multiplier always active, wasting dynamic power
  assign o_result = i_a * i_b;
endmodule

// GOOD — operand isolation gates multiplier inputs
module good_power (
  input  logic        sys_clk, sys_rst_n,
  input  logic        i_valid,
  input  logic [15:0] i_a, i_b,
  output logic [31:0] o_result
);
  logic [15:0] a_gated, b_gated;
  assign a_gated = i_valid ? i_a : '0;  // isolate when invalid
  assign b_gated = i_valid ? i_b : '0;
  assign o_result = a_gated * b_gated;
endmodule


// ============================================================
// EXAMPLE 7: BRAM Inference (FPGA)
// ============================================================

// BAD — async read → distributed RAM (not BRAM)
module bad_bram_inference #(
  parameter int unsigned DEPTH = 1024,
  parameter int unsigned WIDTH = 32
) (
  input  logic                     sys_clk,
  input  logic [$clog2(DEPTH)-1:0] i_addr,
  input  logic [WIDTH-1:0]         i_wdata,
  input  logic                     i_we,
  output logic [WIDTH-1:0]         o_rdata
);
  logic [WIDTH-1:0] mem [0:DEPTH-1];

  always_ff @(posedge sys_clk) begin
    if (i_we) mem[i_addr] <= i_wdata;
  end

  // WRONG: combinational read → cannot map to BRAM
  assign o_rdata = mem[i_addr];
endmodule

// GOOD — synchronous read → BRAM inference
module good_bram_inference #(
  parameter int unsigned DEPTH = 1024,
  parameter int unsigned WIDTH = 32
) (
  input  logic                     sys_clk,
  input  logic [$clog2(DEPTH)-1:0] i_addr,
  input  logic [WIDTH-1:0]         i_wdata,
  input  logic                     i_we,
  output logic [WIDTH-1:0]         o_rdata
);
  logic [WIDTH-1:0] mem [0:DEPTH-1];

  always_ff @(posedge sys_clk) begin
    if (i_we) mem[i_addr] <= i_wdata;
    o_rdata <= mem[i_addr];  // synchronous read → BRAM
  end
endmodule
