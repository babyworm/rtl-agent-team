// perf_monitor_{{MODULE_NAME}}.sv — Performance measurement harness
// Measures latency, throughput, and backpressure statistics for {{MODULE_NAME}}
//
// Usage: Instantiate alongside DUT in the testbench. Read counters after test.
// Compile with +define+PERF_MONITOR to enable (no overhead when disabled).

`ifdef PERF_MONITOR

module perf_monitor_{{MODULE_NAME}} (
  input  logic {{DOMAIN}}_clk,
  input  logic {{DOMAIN}}_rst_n,

  // ─── Handshake signals to monitor ────────────────────────────────────
  input  logic i_valid,       // DUT input valid
  input  logic i_ready,       // DUT input ready (backpressure)
  input  logic o_valid,       // DUT output valid
  input  logic o_ready,       // DUT output ready (downstream backpressure)

  // ─── Measurement outputs ─────────────────────────────────────────────
  output int   o_latency_min,
  output int   o_latency_max,
  output int   o_latency_sum,
  output int   o_txn_count,
  output int   o_throughput_cycles,   // total cycles with valid&&ready output
  output int   o_backpressure_cycles, // total cycles with valid&&!ready input
  output int   o_stall_cycles,        // total cycles with !valid&&ready output (bubble)
  output int   o_total_cycles
);

  // ─── Internal counters ───────────────────────────────────────────────
  int latency_counter;
  logic in_flight;

  initial begin
    o_latency_min = 32'h7FFF_FFFF;
    o_latency_max = 0;
    o_latency_sum = 0;
    o_txn_count   = 0;
    o_throughput_cycles   = 0;
    o_backpressure_cycles = 0;
    o_stall_cycles        = 0;
    o_total_cycles        = 0;
    latency_counter = 0;
    in_flight = 1'b0;
  end

  always_ff @(posedge {{DOMAIN}}_clk or negedge {{DOMAIN}}_rst_n) begin
    if (!{{DOMAIN}}_rst_n) begin
      o_latency_min <= 32'h7FFF_FFFF;
      o_latency_max <= 0;
      o_latency_sum <= 0;
      o_txn_count   <= 0;
      o_throughput_cycles   <= 0;
      o_backpressure_cycles <= 0;
      o_stall_cycles        <= 0;
      o_total_cycles        <= 0;
      latency_counter <= 0;
      in_flight <= 1'b0;
    end else begin
      o_total_cycles <= o_total_cycles + 1;

      // ── Input handshake: start latency measurement ──
      if (i_valid && i_ready) begin
        in_flight <= 1'b1;
        latency_counter <= 0;
      end else if (in_flight) begin
        latency_counter <= latency_counter + 1;
      end

      // ── Output handshake: end latency measurement ──
      if (o_valid && o_ready) begin
        o_throughput_cycles <= o_throughput_cycles + 1;
        o_txn_count <= o_txn_count + 1;
        if (in_flight) begin
          if (latency_counter < o_latency_min) o_latency_min <= latency_counter;
          if (latency_counter > o_latency_max) o_latency_max <= latency_counter;
          o_latency_sum <= o_latency_sum + latency_counter;
          in_flight <= 1'b0;
        end
      end

      // ── Backpressure: input wants to send but DUT not ready ──
      if (i_valid && !i_ready)
        o_backpressure_cycles <= o_backpressure_cycles + 1;

      // ── Stall/bubble: DUT not producing but downstream ready ──
      if (!o_valid && o_ready)
        o_stall_cycles <= o_stall_cycles + 1;
    end
  end

  // ─── Summary report task ─────────────────────────────────────────────
  task automatic print_summary();
    real avg_latency, throughput_pct, backpressure_pct;
    avg_latency = (o_txn_count > 0) ? real'(o_latency_sum) / real'(o_txn_count) : 0.0;
    throughput_pct = (o_total_cycles > 0) ? 100.0 * real'(o_throughput_cycles) / real'(o_total_cycles) : 0.0;
    backpressure_pct = (o_total_cycles > 0) ? 100.0 * real'(o_backpressure_cycles) / real'(o_total_cycles) : 0.0;

    $display("=== Performance Summary: {{MODULE_NAME}} ===");
    $display("  Transactions:    %0d", o_txn_count);
    $display("  Latency (min):   %0d cycles", o_latency_min);
    $display("  Latency (max):   %0d cycles", o_latency_max);
    $display("  Latency (avg):   %.1f cycles", avg_latency);
    $display("  Throughput:      %.1f%% (%0d/%0d cycles)", throughput_pct, o_throughput_cycles, o_total_cycles);
    $display("  Backpressure:    %.1f%% (%0d cycles)", backpressure_pct, o_backpressure_cycles);
    $display("  Stall/bubble:    %0d cycles", o_stall_cycles);
  endtask

endmodule

`endif // PERF_MONITOR
