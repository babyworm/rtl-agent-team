module simple_fifo #(
  parameter int DATA_WIDTH = 32,
  parameter int DEPTH      = 16
) (
  input  logic                  sys_clk,
  input  logic                  sys_rst_n,
  input  logic                  i_push,
  input  logic [DATA_WIDTH-1:0] i_data,
  input  logic                  i_pop,
  output logic [DATA_WIDTH-1:0] o_data,
  output logic                  o_full,
  output logic                  o_empty
);
  logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];
endmodule
