// Standard SRAM Wrapper — Two-Port (TP)
// Deploy to: rtl/common/sram_tp.sv
// Separate read and write ports, SINGLE clock. Use for simultaneous read+write
// within the same clock domain. Instance naming: `u_mem_{purpose}`.
// For synthesis, add the sram_sp-style `ifdef compiled-macro branches above the
// behavioral block; the behavioral body stays translate_off-guarded.
module sram_tp #(
  parameter int DEPTH = 256,
  parameter int WIDTH = 32
) (
  input  logic                    clk,
  // Write port
  input  logic                    i_wen,
  input  logic [$clog2(DEPTH)-1:0] i_waddr,
  input  logic [WIDTH-1:0]        i_wdata,
  // Read port
  input  logic                    i_ren,
  input  logic [$clog2(DEPTH)-1:0] i_raddr,
  output logic [WIDTH-1:0]        o_rdata
);

  // Behavioral model — SIMULATION ONLY
  // synopsys translate_off
  logic [WIDTH-1:0] mem [0:DEPTH-1];

  always_ff @(posedge clk) begin
    if (i_wen) begin
      mem[i_waddr] <= i_wdata;
    end
    if (i_ren) begin
      o_rdata <= mem[i_raddr];  // 1-cycle read latency
    end
  end
  // synopsys translate_on

endmodule
