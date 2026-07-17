// dut_top — integration example with TWO INTENTIONAL connectivity bugs:
//   1. width_mismatch: `pix` is 8 bits but u_pack.i_data expects DATA_W=16.
//   2. dangling_port:  u_pack.o_word_valid is left explicitly unconnected.
// check_connectivity.py must report exactly these two violations.
module dut_top (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        i_en,
  output logic [31:0] o_word,
  output logic        o_word_valid
);

  logic [7:0] pix;
  logic       pix_valid;

  pixel_gen #(
    .PIX_W (8)
  ) u_gen (
    .clk         (clk),
    .rst_n       (rst_n),
    .i_en        (i_en),
    .o_pix       (pix),
    .o_pix_valid (pix_valid)
  );

  pixel_pack u_pack (
    .clk          (clk),
    .rst_n        (rst_n),
    .i_data       (pix),          // BUG 1: 8-bit signal into 16-bit port
    .i_data_valid (pix_valid),
    .o_word       (o_word),
    .o_word_valid ()              // BUG 2: dangling output pin
  );

  assign o_word_valid = pix_valid;

endmodule
