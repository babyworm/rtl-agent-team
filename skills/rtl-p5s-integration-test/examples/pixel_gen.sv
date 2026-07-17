// pixel_gen — free-running pixel pattern generator (worked example, clean).
module pixel_gen #(
  parameter int PIX_W = 8
) (
  input  logic             clk,
  input  logic             rst_n,
  input  logic             i_en,
  output logic [PIX_W-1:0] o_pix,
  output logic             o_pix_valid
);

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      o_pix       <= '0;
      o_pix_valid <= 1'b0;
    end else begin
      if (i_en) begin
        o_pix <= o_pix + PIX_W'(1);
      end
      o_pix_valid <= i_en;
    end
  end

endmodule
