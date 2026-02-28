// =============================================================================
// RTL Agent Team - SystemVerilog Testbench Template
// Domain: Video Codec (H.264/H.265)
// =============================================================================
// Usage: Copy this template and customize for your specific module.
//        Replace {MODULE_NAME}, {DATA_WIDTH}, etc. with actual values.
// =============================================================================

`timescale 1ns / 1ps

module tb_{MODULE_NAME};

  // =========================================================================
  // Parameters
  // =========================================================================
  parameter int unsigned DATA_WIDTH = {DATA_WIDTH};
  localparam int L_CLK_PERIOD = 10; // ns (100 MHz)

  // =========================================================================
  // DUT Signals
  // =========================================================================
  logic                    clk;
  logic                    rst_n;
  // TODO: Add DUT-specific ports here
  // logic [DATA_WIDTH-1:0]  i_data;
  // logic                    i_valid;
  // logic                    o_ready;
  // logic [DATA_WIDTH-1:0]  o_data;
  // logic                    o_valid;

  // =========================================================================
  // Clock Generation
  // =========================================================================
  initial clk = 1'b0;
  always #(L_CLK_PERIOD/2) clk = ~clk;

  // =========================================================================
  // DUT Instantiation
  // =========================================================================
  {MODULE_NAME} #(
    .DATA_WIDTH(DATA_WIDTH)
  ) u_dut (
    .clk    (clk),
    .rst_n  (rst_n)
    // TODO: Connect ports
  );

  // =========================================================================
  // Test Vector Loading (from Reference Model)
  // =========================================================================
  // integer fd_input, fd_expected;
  // logic [DATA_WIDTH-1:0] expected_output;
  //
  // initial begin
  //   fd_input    = $fopen("refc/vectors/inputs.txt", "r");
  //   fd_expected = $fopen("refc/vectors/expected.txt", "r");
  // end

  // =========================================================================
  // Reset Task
  // =========================================================================
  task automatic do_reset(int cycles = 5);
    rst_n <= 1'b0;
    repeat(cycles) @(posedge clk);
    rst_n <= 1'b1;
    @(posedge clk);
  endtask

  // =========================================================================
  // Stimulus Task
  // =========================================================================
  // task automatic apply_stimulus(input logic [DATA_WIDTH-1:0] data);
  //   @(posedge clk);
  //   i_data  <= data;
  //   i_valid <= 1'b1;
  //   @(posedge clk);
  //   while (!o_ready) @(posedge clk);
  //   i_valid <= 1'b0;
  // endtask

  // =========================================================================
  // Checker Task
  // =========================================================================
  // task automatic check_output(
  //   input logic [DATA_WIDTH-1:0] expected,
  //   input int vector_num
  // );
  //   @(posedge clk);
  //   while (!o_valid) @(posedge clk);
  //   if (o_data !== expected) begin
  //     $error("MISMATCH at vector %0d: got=0x%h, expected=0x%h",
  //            vector_num, o_data, expected);
  //   end
  // endtask

  // =========================================================================
  // Main Test Sequence
  // =========================================================================
  initial begin
    $display("=== TB_%0s START ===", "{MODULE_NAME}");

    // Reset
    do_reset();

    // TODO: Apply test vectors and check results
    // for (int i = 0; i < NUM_VECTORS; i++) begin
    //   apply_stimulus(input_vectors[i]);
    //   check_output(expected_vectors[i], i);
    // end

    $display("=== TB_%0s COMPLETE: ALL TESTS PASSED ===", "{MODULE_NAME}");
    $finish(0);
  end

  // =========================================================================
  // Timeout Watchdog
  // =========================================================================
  initial begin
    #(L_CLK_PERIOD * 1_000_000); // 10ms timeout
    $error("TIMEOUT: Test did not complete in time");
    $finish(1);
  end

  // =========================================================================
  // Waveform Dump (conditional)
  // =========================================================================
  `ifdef DUMP_WAVES
  initial begin
    $dumpfile("tb_{MODULE_NAME}.vcd");
    $dumpvars(0, tb_{MODULE_NAME});
  end
  `endif

endmodule
