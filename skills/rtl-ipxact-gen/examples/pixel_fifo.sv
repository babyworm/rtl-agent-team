// pixel_fifo.sv — tiny synchronous FIFO used as the gen_ipxact.py demo input.
// Demonstrates: i_/o_ port prefixes, clk/rst_n exemption, parameterized
// widths that must survive into the IP-XACT XML as expressions (never
// resolved to literals), and a $clog2-derived status port width.
module pixel_fifo #(
  parameter int DATA_WIDTH = 8,
  parameter int DEPTH      = 16
) (
  input  logic                     clk,
  input  logic                     rst_n,

  // Write side
  input  logic                     i_wr_valid,
  input  logic [DATA_WIDTH-1:0]    i_wr_data,
  output logic                     o_wr_ready,

  // Read side
  output logic                     o_rd_valid,
  output logic [DATA_WIDTH-1:0]    o_rd_data,
  input  logic                     i_rd_ready,

  // Status
  output logic [$clog2(DEPTH):0]   o_level
);

  localparam int L_PTR_W = $clog2(DEPTH);

  logic [DATA_WIDTH-1:0] mem [DEPTH];
  logic [L_PTR_W:0]      wr_ptr;
  logic [L_PTR_W:0]      rd_ptr;

  assign o_level    = wr_ptr - rd_ptr;
  assign o_wr_ready = (o_level != DEPTH[$clog2(DEPTH):0]);
  assign o_rd_valid = (o_level != '0);
  assign o_rd_data  = mem[rd_ptr[L_PTR_W-1:0]];

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      wr_ptr <= '0;
      rd_ptr <= '0;
    end else begin
      if (i_wr_valid && o_wr_ready) begin
        mem[wr_ptr[L_PTR_W-1:0]] <= i_wr_data;
        wr_ptr                   <= wr_ptr + 1'b1;
      end
      if (o_rd_valid && i_rd_ready) begin
        rd_ptr <= rd_ptr + 1'b1;
      end
    end
  end

endmodule
