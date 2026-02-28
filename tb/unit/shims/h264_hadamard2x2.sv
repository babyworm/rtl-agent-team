// =============================================================================
// iverilog-compatible shim for h264_hadamard2x2
// Functionally identical to rtl/itq/h264_hadamard2x2.sv but avoids
// always_comb / always_ff / SystemVerilog type casts (unsupported by iverilog 12).
// =============================================================================

module h264_hadamard2x2 #(
    parameter DATA_WIDTH = 16
) (
    input  wire                         sys_clk,
    input  wire                         sys_rst_n,

    input  wire                         i_valid,
    output wire                         o_ready,
    input  wire [4*DATA_WIDTH-1:0]      i_block,
    input  wire                         i_mode,

    output wire                         o_valid,
    input  wire                         i_ready,
    output wire [4*DATA_WIDTH-1:0]      o_block
);

    localparam L_SUM_WIDTH = DATA_WIDTH + 2;

    // -------------------------------------------------------------------------
    // Input unpacking
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] in_a = i_block[0*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_b = i_block[1*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_c = i_block[2*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_d = i_block[3*DATA_WIDTH +: DATA_WIDTH];

    // -------------------------------------------------------------------------
    // Sign-extend inputs
    // -------------------------------------------------------------------------
    wire signed [L_SUM_WIDTH-1:0] ext_a = {{2{in_a[DATA_WIDTH-1]}}, in_a};
    wire signed [L_SUM_WIDTH-1:0] ext_b = {{2{in_b[DATA_WIDTH-1]}}, in_b};
    wire signed [L_SUM_WIDTH-1:0] ext_c = {{2{in_c[DATA_WIDTH-1]}}, in_c};
    wire signed [L_SUM_WIDTH-1:0] ext_d = {{2{in_d[DATA_WIDTH-1]}}, in_d};

    // -------------------------------------------------------------------------
    // Combinational Hadamard 2x2 butterfly
    // -------------------------------------------------------------------------
    reg signed [L_SUM_WIDTH-1:0] comb_y0, comb_y1, comb_y2, comb_y3;

    always @(*) begin
        comb_y0 = ext_a + ext_b + ext_c + ext_d;
        comb_y1 = ext_a - ext_b + ext_c - ext_d;
        comb_y2 = ext_a + ext_b - ext_c - ext_d;
        comb_y3 = ext_a - ext_b - ext_c + ext_d;
    end

    // -------------------------------------------------------------------------
    // Output truncation to DATA_WIDTH
    // Forward (i_mode=0): direct truncation
    // Inverse (i_mode=1): arithmetic right shift by 1 (>>>1 normalization)
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] trunc_y0 = i_mode ? (comb_y0 >>> 1) : comb_y0[DATA_WIDTH-1:0];
    wire signed [DATA_WIDTH-1:0] trunc_y1 = i_mode ? (comb_y1 >>> 1) : comb_y1[DATA_WIDTH-1:0];
    wire signed [DATA_WIDTH-1:0] trunc_y2 = i_mode ? (comb_y2 >>> 1) : comb_y2[DATA_WIDTH-1:0];
    wire signed [DATA_WIDTH-1:0] trunc_y3 = i_mode ? (comb_y3 >>> 1) : comb_y3[DATA_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Output register with valid/ready handshake
    // -------------------------------------------------------------------------
    reg [4*DATA_WIDTH-1:0] out_block_reg;
    reg                    out_valid_reg;

    assign o_ready = ~out_valid_reg | i_ready;

    always @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            out_valid_reg <= 1'b0;
            out_block_reg <= 0;
        end else if (o_valid & i_ready) begin
            if (i_valid) begin
                out_valid_reg <= 1'b1;
                out_block_reg <= {trunc_y3, trunc_y2, trunc_y1, trunc_y0};
            end else begin
                out_valid_reg <= 1'b0;
            end
        end else if (i_valid & o_ready) begin
            out_valid_reg <= 1'b1;
            out_block_reg <= {trunc_y3, trunc_y2, trunc_y1, trunc_y0};
        end
    end

    assign o_valid = out_valid_reg;
    assign o_block = out_block_reg;

endmodule
