// pixel_pack — packs two DATA_W samples into one WORD_W word (worked example, clean).
module pixel_pack #(
  parameter int DATA_W = 16,
  parameter int WORD_W = 32
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic [DATA_W-1:0] i_data,
  input  logic              i_data_valid,
  output logic [WORD_W-1:0] o_word,
  output logic              o_word_valid
);

  logic [DATA_W-1:0] data_q;
  logic              phase_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      data_q       <= '0;
      phase_q      <= 1'b0;
      o_word       <= '0;
      o_word_valid <= 1'b0;
    end else begin
      o_word_valid <= 1'b0;
      if (i_data_valid) begin
        phase_q <= ~phase_q;
        if (phase_q) begin
          o_word       <= {data_q, i_data};
          o_word_valid <= 1'b1;
        end else begin
          data_q <= i_data;
        end
      end
    end
  end

endmodule
