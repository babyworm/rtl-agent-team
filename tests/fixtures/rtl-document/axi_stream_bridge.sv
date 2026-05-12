module axi_stream_bridge #(
  parameter int DATA_WIDTH = 64
) (
  input  logic                  sys_clk,
  input  logic                  sys_rst_n,
  input  logic                  pixel_clk,
  input  logic                  pixel_rst_n,
  // APB control (sys domain)
  input  logic                  i_psel,
  input  logic                  i_penable,
  input  logic [31:0]           i_paddr,
  // AXI-Stream egress (pixel domain)
  output logic [DATA_WIDTH-1:0] o_tdata,
  output logic                  o_tvalid,
  input  logic                  i_tready
);
  async_fifo #(.WIDTH(DATA_WIDTH)) u_ingress_fifo (.*);
  async_fifo #(.WIDTH(DATA_WIDTH)) u_egress_fifo  (.*);
endmodule
