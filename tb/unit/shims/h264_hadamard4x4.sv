// =============================================================================
// iverilog-compatible shim for h264_hadamard4x4
// Functionally identical to rtl/itq/h264_hadamard4x4.sv but avoids
// 'automatic' variables inside always blocks (unsupported by iverilog 12).
// =============================================================================

module h264_hadamard4x4 #(
    parameter DATA_WIDTH = 16
) (
    input  wire                          sys_clk,
    input  wire                          sys_rst_n,

    input  wire                          i_valid,
    output wire                          o_ready,
    input  wire [16*DATA_WIDTH-1:0]      i_block,
    input  wire                          i_mode,

    output wire                          o_valid,
    input  wire                          i_ready,
    output wire [16*DATA_WIDTH-1:0]      o_block
);

    localparam L_EXT_WIDTH = DATA_WIDTH + 2;
    localparam L_COL_WIDTH = L_EXT_WIDTH + 2;

    // -------------------------------------------------------------------------
    // Input unpacking
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] in_elem_0_0 = i_block[ 0*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_0_1 = i_block[ 1*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_0_2 = i_block[ 2*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_0_3 = i_block[ 3*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_1_0 = i_block[ 4*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_1_1 = i_block[ 5*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_1_2 = i_block[ 6*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_1_3 = i_block[ 7*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_2_0 = i_block[ 8*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_2_1 = i_block[ 9*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_2_2 = i_block[10*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_2_3 = i_block[11*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_3_0 = i_block[12*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_3_1 = i_block[13*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_3_2 = i_block[14*DATA_WIDTH +: DATA_WIDTH];
    wire signed [DATA_WIDTH-1:0] in_elem_3_3 = i_block[15*DATA_WIDTH +: DATA_WIDTH];

    // -------------------------------------------------------------------------
    // Stage 1: Row-wise butterfly (combinational) — unrolled
    // -------------------------------------------------------------------------
    reg signed [L_EXT_WIDTH-1:0] row_result_0_0, row_result_0_1, row_result_0_2, row_result_0_3;
    reg signed [L_EXT_WIDTH-1:0] row_result_1_0, row_result_1_1, row_result_1_2, row_result_1_3;
    reg signed [L_EXT_WIDTH-1:0] row_result_2_0, row_result_2_1, row_result_2_2, row_result_2_3;
    reg signed [L_EXT_WIDTH-1:0] row_result_3_0, row_result_3_1, row_result_3_2, row_result_3_3;

    // Row temporaries
    reg signed [DATA_WIDTH:0] rp0_0, rp1_0, rp2_0, rp3_0;
    reg signed [DATA_WIDTH:0] rp0_1, rp1_1, rp2_1, rp3_1;
    reg signed [DATA_WIDTH:0] rp0_2, rp1_2, rp2_2, rp3_2;
    reg signed [DATA_WIDTH:0] rp0_3, rp1_3, rp2_3, rp3_3;

    always @(*) begin
        // Row 0
        rp0_0 = $signed(in_elem_0_0) + $signed(in_elem_0_1);
        rp1_0 = $signed(in_elem_0_2) + $signed(in_elem_0_3);
        rp2_0 = $signed(in_elem_0_0) - $signed(in_elem_0_1);
        rp3_0 = $signed(in_elem_0_2) - $signed(in_elem_0_3);
        row_result_0_0 = rp0_0 + rp1_0;
        row_result_0_1 = rp2_0 + rp3_0;
        row_result_0_2 = rp0_0 - rp1_0;
        row_result_0_3 = rp2_0 - rp3_0;

        // Row 1
        rp0_1 = $signed(in_elem_1_0) + $signed(in_elem_1_1);
        rp1_1 = $signed(in_elem_1_2) + $signed(in_elem_1_3);
        rp2_1 = $signed(in_elem_1_0) - $signed(in_elem_1_1);
        rp3_1 = $signed(in_elem_1_2) - $signed(in_elem_1_3);
        row_result_1_0 = rp0_1 + rp1_1;
        row_result_1_1 = rp2_1 + rp3_1;
        row_result_1_2 = rp0_1 - rp1_1;
        row_result_1_3 = rp2_1 - rp3_1;

        // Row 2
        rp0_2 = $signed(in_elem_2_0) + $signed(in_elem_2_1);
        rp1_2 = $signed(in_elem_2_2) + $signed(in_elem_2_3);
        rp2_2 = $signed(in_elem_2_0) - $signed(in_elem_2_1);
        rp3_2 = $signed(in_elem_2_2) - $signed(in_elem_2_3);
        row_result_2_0 = rp0_2 + rp1_2;
        row_result_2_1 = rp2_2 + rp3_2;
        row_result_2_2 = rp0_2 - rp1_2;
        row_result_2_3 = rp2_2 - rp3_2;

        // Row 3
        rp0_3 = $signed(in_elem_3_0) + $signed(in_elem_3_1);
        rp1_3 = $signed(in_elem_3_2) + $signed(in_elem_3_3);
        rp2_3 = $signed(in_elem_3_0) - $signed(in_elem_3_1);
        rp3_3 = $signed(in_elem_3_2) - $signed(in_elem_3_3);
        row_result_3_0 = rp0_3 + rp1_3;
        row_result_3_1 = rp2_3 + rp3_3;
        row_result_3_2 = rp0_3 - rp1_3;
        row_result_3_3 = rp2_3 - rp3_3;
    end

    // -------------------------------------------------------------------------
    // Stage 1 register
    // -------------------------------------------------------------------------
    reg signed [L_EXT_WIDTH-1:0] stage1_0_0, stage1_0_1, stage1_0_2, stage1_0_3;
    reg signed [L_EXT_WIDTH-1:0] stage1_1_0, stage1_1_1, stage1_1_2, stage1_1_3;
    reg signed [L_EXT_WIDTH-1:0] stage1_2_0, stage1_2_1, stage1_2_2, stage1_2_3;
    reg signed [L_EXT_WIDTH-1:0] stage1_3_0, stage1_3_1, stage1_3_2, stage1_3_3;
    reg        mode_s1;
    reg        valid_s1;

    wire stall_s1;
    assign stall_s1 = valid_s1 & ~(i_ready | ~o_valid);
    assign o_ready  = ~stall_s1;

    always @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            valid_s1   <= 1'b0;
            mode_s1    <= 1'b0;
            stage1_0_0 <= 0; stage1_0_1 <= 0; stage1_0_2 <= 0; stage1_0_3 <= 0;
            stage1_1_0 <= 0; stage1_1_1 <= 0; stage1_1_2 <= 0; stage1_1_3 <= 0;
            stage1_2_0 <= 0; stage1_2_1 <= 0; stage1_2_2 <= 0; stage1_2_3 <= 0;
            stage1_3_0 <= 0; stage1_3_1 <= 0; stage1_3_2 <= 0; stage1_3_3 <= 0;
        end else if (!stall_s1) begin
            valid_s1   <= i_valid;
            mode_s1    <= i_mode;
            stage1_0_0 <= row_result_0_0; stage1_0_1 <= row_result_0_1;
            stage1_0_2 <= row_result_0_2; stage1_0_3 <= row_result_0_3;
            stage1_1_0 <= row_result_1_0; stage1_1_1 <= row_result_1_1;
            stage1_1_2 <= row_result_1_2; stage1_1_3 <= row_result_1_3;
            stage1_2_0 <= row_result_2_0; stage1_2_1 <= row_result_2_1;
            stage1_2_2 <= row_result_2_2; stage1_2_3 <= row_result_2_3;
            stage1_3_0 <= row_result_3_0; stage1_3_1 <= row_result_3_1;
            stage1_3_2 <= row_result_3_2; stage1_3_3 <= row_result_3_3;
        end
    end

    // -------------------------------------------------------------------------
    // Stage 2: Column-wise butterfly (combinational) — unrolled
    // -------------------------------------------------------------------------
    reg signed [L_COL_WIDTH-1:0] col_result_0_0, col_result_0_1, col_result_0_2, col_result_0_3;
    reg signed [L_COL_WIDTH-1:0] col_result_1_0, col_result_1_1, col_result_1_2, col_result_1_3;
    reg signed [L_COL_WIDTH-1:0] col_result_2_0, col_result_2_1, col_result_2_2, col_result_2_3;
    reg signed [L_COL_WIDTH-1:0] col_result_3_0, col_result_3_1, col_result_3_2, col_result_3_3;

    reg signed [L_EXT_WIDTH:0] cp0_0, cp1_0, cp2_0, cp3_0;
    reg signed [L_EXT_WIDTH:0] cp0_1, cp1_1, cp2_1, cp3_1;
    reg signed [L_EXT_WIDTH:0] cp0_2, cp1_2, cp2_2, cp3_2;
    reg signed [L_EXT_WIDTH:0] cp0_3, cp1_3, cp2_3, cp3_3;

    always @(*) begin
        // Col 0
        cp0_0 = $signed(stage1_0_0) + $signed(stage1_1_0);
        cp1_0 = $signed(stage1_2_0) + $signed(stage1_3_0);
        cp2_0 = $signed(stage1_0_0) - $signed(stage1_1_0);
        cp3_0 = $signed(stage1_2_0) - $signed(stage1_3_0);
        col_result_0_0 = cp0_0 + cp1_0;
        col_result_1_0 = cp2_0 + cp3_0;
        col_result_2_0 = cp0_0 - cp1_0;
        col_result_3_0 = cp2_0 - cp3_0;

        // Col 1
        cp0_1 = $signed(stage1_0_1) + $signed(stage1_1_1);
        cp1_1 = $signed(stage1_2_1) + $signed(stage1_3_1);
        cp2_1 = $signed(stage1_0_1) - $signed(stage1_1_1);
        cp3_1 = $signed(stage1_2_1) - $signed(stage1_3_1);
        col_result_0_1 = cp0_1 + cp1_1;
        col_result_1_1 = cp2_1 + cp3_1;
        col_result_2_1 = cp0_1 - cp1_1;
        col_result_3_1 = cp2_1 - cp3_1;

        // Col 2
        cp0_2 = $signed(stage1_0_2) + $signed(stage1_1_2);
        cp1_2 = $signed(stage1_2_2) + $signed(stage1_3_2);
        cp2_2 = $signed(stage1_0_2) - $signed(stage1_1_2);
        cp3_2 = $signed(stage1_2_2) - $signed(stage1_3_2);
        col_result_0_2 = cp0_2 + cp1_2;
        col_result_1_2 = cp2_2 + cp3_2;
        col_result_2_2 = cp0_2 - cp1_2;
        col_result_3_2 = cp2_2 - cp3_2;

        // Col 3
        cp0_3 = $signed(stage1_0_3) + $signed(stage1_1_3);
        cp1_3 = $signed(stage1_2_3) + $signed(stage1_3_3);
        cp2_3 = $signed(stage1_0_3) - $signed(stage1_1_3);
        cp3_3 = $signed(stage1_2_3) - $signed(stage1_3_3);
        col_result_0_3 = cp0_3 + cp1_3;
        col_result_1_3 = cp2_3 + cp3_3;
        col_result_2_3 = cp0_3 - cp1_3;
        col_result_3_3 = cp2_3 - cp3_3;
    end

    // -------------------------------------------------------------------------
    // Output: truncate/normalize — unrolled
    // -------------------------------------------------------------------------
    reg signed [DATA_WIDTH-1:0] out_elem_0_0, out_elem_0_1, out_elem_0_2, out_elem_0_3;
    reg signed [DATA_WIDTH-1:0] out_elem_1_0, out_elem_1_1, out_elem_1_2, out_elem_1_3;
    reg signed [DATA_WIDTH-1:0] out_elem_2_0, out_elem_2_1, out_elem_2_2, out_elem_2_3;
    reg signed [DATA_WIDTH-1:0] out_elem_3_0, out_elem_3_1, out_elem_3_2, out_elem_3_3;

    always @(*) begin
        if (mode_s1) begin
            // Inverse: arithmetic right shift by 1
            out_elem_0_0 = (col_result_0_0 >>> 1); out_elem_0_1 = (col_result_0_1 >>> 1);
            out_elem_0_2 = (col_result_0_2 >>> 1); out_elem_0_3 = (col_result_0_3 >>> 1);
            out_elem_1_0 = (col_result_1_0 >>> 1); out_elem_1_1 = (col_result_1_1 >>> 1);
            out_elem_1_2 = (col_result_1_2 >>> 1); out_elem_1_3 = (col_result_1_3 >>> 1);
            out_elem_2_0 = (col_result_2_0 >>> 1); out_elem_2_1 = (col_result_2_1 >>> 1);
            out_elem_2_2 = (col_result_2_2 >>> 1); out_elem_2_3 = (col_result_2_3 >>> 1);
            out_elem_3_0 = (col_result_3_0 >>> 1); out_elem_3_1 = (col_result_3_1 >>> 1);
            out_elem_3_2 = (col_result_3_2 >>> 1); out_elem_3_3 = (col_result_3_3 >>> 1);
        end else begin
            // Forward: truncate to DATA_WIDTH
            out_elem_0_0 = col_result_0_0[DATA_WIDTH-1:0]; out_elem_0_1 = col_result_0_1[DATA_WIDTH-1:0];
            out_elem_0_2 = col_result_0_2[DATA_WIDTH-1:0]; out_elem_0_3 = col_result_0_3[DATA_WIDTH-1:0];
            out_elem_1_0 = col_result_1_0[DATA_WIDTH-1:0]; out_elem_1_1 = col_result_1_1[DATA_WIDTH-1:0];
            out_elem_1_2 = col_result_1_2[DATA_WIDTH-1:0]; out_elem_1_3 = col_result_1_3[DATA_WIDTH-1:0];
            out_elem_2_0 = col_result_2_0[DATA_WIDTH-1:0]; out_elem_2_1 = col_result_2_1[DATA_WIDTH-1:0];
            out_elem_2_2 = col_result_2_2[DATA_WIDTH-1:0]; out_elem_2_3 = col_result_2_3[DATA_WIDTH-1:0];
            out_elem_3_0 = col_result_3_0[DATA_WIDTH-1:0]; out_elem_3_1 = col_result_3_1[DATA_WIDTH-1:0];
            out_elem_3_2 = col_result_3_2[DATA_WIDTH-1:0]; out_elem_3_3 = col_result_3_3[DATA_WIDTH-1:0];
        end
    end

    // -------------------------------------------------------------------------
    // Output register with handshake
    // -------------------------------------------------------------------------
    reg [16*DATA_WIDTH-1:0] out_block_reg;
    reg                     out_valid_reg;

    always @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            out_valid_reg <= 1'b0;
            out_block_reg <= 0;
        end else if (o_valid & i_ready) begin
            out_valid_reg <= 1'b0;
        end else if (valid_s1 & (~o_valid | i_ready)) begin
            out_valid_reg <= 1'b1;
            out_block_reg[ 0*DATA_WIDTH +: DATA_WIDTH] <= out_elem_0_0;
            out_block_reg[ 1*DATA_WIDTH +: DATA_WIDTH] <= out_elem_0_1;
            out_block_reg[ 2*DATA_WIDTH +: DATA_WIDTH] <= out_elem_0_2;
            out_block_reg[ 3*DATA_WIDTH +: DATA_WIDTH] <= out_elem_0_3;
            out_block_reg[ 4*DATA_WIDTH +: DATA_WIDTH] <= out_elem_1_0;
            out_block_reg[ 5*DATA_WIDTH +: DATA_WIDTH] <= out_elem_1_1;
            out_block_reg[ 6*DATA_WIDTH +: DATA_WIDTH] <= out_elem_1_2;
            out_block_reg[ 7*DATA_WIDTH +: DATA_WIDTH] <= out_elem_1_3;
            out_block_reg[ 8*DATA_WIDTH +: DATA_WIDTH] <= out_elem_2_0;
            out_block_reg[ 9*DATA_WIDTH +: DATA_WIDTH] <= out_elem_2_1;
            out_block_reg[10*DATA_WIDTH +: DATA_WIDTH] <= out_elem_2_2;
            out_block_reg[11*DATA_WIDTH +: DATA_WIDTH] <= out_elem_2_3;
            out_block_reg[12*DATA_WIDTH +: DATA_WIDTH] <= out_elem_3_0;
            out_block_reg[13*DATA_WIDTH +: DATA_WIDTH] <= out_elem_3_1;
            out_block_reg[14*DATA_WIDTH +: DATA_WIDTH] <= out_elem_3_2;
            out_block_reg[15*DATA_WIDTH +: DATA_WIDTH] <= out_elem_3_3;
        end
    end

    assign o_valid = out_valid_reg;
    assign o_block = out_block_reg;

endmodule
