module cabac_encoder_excerpt #(
  parameter int CTX_WIDTH = 7
) (
  input  logic                  sys_clk,
  input  logic                  sys_rst_n,
  input  logic                  i_valid,
  input  logic [CTX_WIDTH-1:0]  i_ctx_idx,
  input  logic                  i_bin,
  output logic [7:0]            o_byte,
  output logic                  o_byte_valid
);
  typedef enum logic [1:0] {
    ST_IDLE   = 2'd0,
    ST_ENCODE = 2'd1,
    ST_FLUSH  = 2'd2
  } state_e;

  state_e state, next_state;

  range_coder        u_range_coder        (.*);
  context_memory     u_context_memory     (.*);
  bypass_encoder     u_bypass_encoder     (.*);

  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) state <= ST_IDLE;
    else            state <= next_state;
  end
endmodule
