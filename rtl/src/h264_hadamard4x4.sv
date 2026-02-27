// =============================================================================
// Module: h264_hadamard4x4
// Description: 2-stage pipelined 4x4 Hadamard transform for H.264 luma DC
//              coefficients. Forward and inverse use the same butterfly;
//              inverse applies >>1 normalization at the output.
// =============================================================================

module h264_hadamard4x4 #(
    parameter DATA_WIDTH = 16
) (
    input  logic                          sys_clk,
    input  logic                          sys_rst_n,

    // Input handshake
    input  logic                          i_valid,
    output logic                          o_ready,
    input  logic [16*DATA_WIDTH-1:0]      i_block,
    input  logic                          i_mode,     // 0=forward, 1=inverse

    // Output handshake
    output logic                          o_valid,
    input  logic                          i_ready,
    output logic [16*DATA_WIDTH-1:0]      o_block
);

    // -------------------------------------------------------------------------
    // Local parameters
    // -------------------------------------------------------------------------
    localparam L_EXT_WIDTH = DATA_WIDTH + 2;  // 18 bits after row butterfly
    localparam L_COL_WIDTH = L_EXT_WIDTH + 2; // 20 bits after col butterfly

    // -------------------------------------------------------------------------
    // Input unpacking — 4x4 matrix of signed elements
    // -------------------------------------------------------------------------
    logic signed [DATA_WIDTH-1:0] in_elem [0:3][0:3];

    genvar gi, gj;
    generate
        for (gi = 0; gi < 4; gi++) begin : gen_unpack_row
            for (gj = 0; gj < 4; gj++) begin : gen_unpack_col
                assign in_elem[gi][gj] = i_block[(gi*4+gj)*DATA_WIDTH +: DATA_WIDTH];
            end
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Stage 1: Row-wise butterfly (combinational)
    // -------------------------------------------------------------------------
    logic signed [L_EXT_WIDTH-1:0] row_result [0:3][0:3];

    always_comb begin
        for (int r = 0; r < 4; r++) begin
            automatic logic signed [DATA_WIDTH:0] p0, p1, p2, p3;
            p0 = in_elem[r][0] + in_elem[r][1];
            p1 = in_elem[r][2] + in_elem[r][3];
            p2 = in_elem[r][0] - in_elem[r][1];
            p3 = in_elem[r][2] - in_elem[r][3];

            row_result[r][0] = p0 + p1;
            row_result[r][1] = p2 + p3;
            row_result[r][2] = p0 - p1;
            row_result[r][3] = p2 - p3;
        end
    end

    // -------------------------------------------------------------------------
    // Stage 1 register
    // -------------------------------------------------------------------------
    logic signed [L_EXT_WIDTH-1:0] stage1_reg [0:3][0:3];
    logic                          mode_s1;
    logic                          valid_s1;

    // Pipeline control
    logic stall_s1;
    assign stall_s1 = valid_s1 & ~(i_ready | ~o_valid);
    assign o_ready  = ~stall_s1;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            valid_s1 <= 1'b0;
            mode_s1  <= 1'b0;
            for (int r = 0; r < 4; r++) begin
                for (int c = 0; c < 4; c++) begin
                    stage1_reg[r][c] <= '0;
                end
            end
        end else if (!stall_s1) begin
            valid_s1 <= i_valid;
            mode_s1  <= i_mode;
            for (int r = 0; r < 4; r++) begin
                for (int c = 0; c < 4; c++) begin
                    stage1_reg[r][c] <= row_result[r][c];
                end
            end
        end
    end

    // -------------------------------------------------------------------------
    // Stage 2: Column-wise butterfly (combinational)
    // -------------------------------------------------------------------------
    logic signed [L_COL_WIDTH-1:0] col_result [0:3][0:3];

    always_comb begin
        for (int c = 0; c < 4; c++) begin
            automatic logic signed [L_EXT_WIDTH:0] p0, p1, p2, p3;
            p0 = stage1_reg[0][c] + stage1_reg[1][c];
            p1 = stage1_reg[2][c] + stage1_reg[3][c];
            p2 = stage1_reg[0][c] - stage1_reg[1][c];
            p3 = stage1_reg[2][c] - stage1_reg[3][c];

            col_result[0][c] = p0 + p1;
            col_result[1][c] = p2 + p3;
            col_result[2][c] = p0 - p1;
            col_result[3][c] = p2 - p3;
        end
    end

    // -------------------------------------------------------------------------
    // Output: truncate/normalize and register
    // -------------------------------------------------------------------------
    logic signed [DATA_WIDTH-1:0] out_elem [0:3][0:3];

    always_comb begin
        for (int r = 0; r < 4; r++) begin
            for (int c = 0; c < 4; c++) begin
                if (mode_s1) begin
                    // Inverse: arithmetic right shift by 1, explicit truncate
                    out_elem[r][c] = DATA_WIDTH'((col_result[r][c] >>> 1));
                end else begin
                    // Forward: truncate to DATA_WIDTH
                    out_elem[r][c] = col_result[r][c][DATA_WIDTH-1:0];
                end
            end
        end
    end

    // -------------------------------------------------------------------------
    // Output register with handshake
    // -------------------------------------------------------------------------
    logic [16*DATA_WIDTH-1:0] out_block_reg;
    logic                     out_valid_reg;

    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            out_valid_reg <= 1'b0;
            out_block_reg <= '0;
        end else if (o_valid & i_ready) begin
            // Output consumed
            out_valid_reg <= 1'b0;
        end else if (valid_s1 & (~o_valid | i_ready)) begin
            out_valid_reg <= 1'b1;
            for (int r = 0; r < 4; r++) begin
                for (int c = 0; c < 4; c++) begin
                    out_block_reg[(r*4+c)*DATA_WIDTH +: DATA_WIDTH] <= out_elem[r][c];
                end
            end
        end
    end

    assign o_valid = out_valid_reg;
    assign o_block = out_block_reg;

endmodule
