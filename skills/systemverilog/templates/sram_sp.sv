// Standard SRAM Wrapper — Single-Port (SP)
// Deploy to: rtl/common/sram_sp.sv
// One R/W port, single clock. Instance naming: `u_mem_{purpose}`.
// Synthesis: behavioral array is translate_off-guarded (DC/Genus skip it);
// compiled-macro branches activate via `+define+RAT_MEM_<PROCESS>`
// (passed by `run_syn.sh --mem-process`; pair with `--mem-lib` for real timing).
module sram_sp #(
  parameter int DEPTH = 256,
  parameter int WIDTH = 32
) (
  input  logic                    clk,
  input  logic                    i_ce,
  input  logic                    i_we,
  input  logic [$clog2(DEPTH)-1:0] i_addr,
  input  logic [WIDTH-1:0]        i_wdata,
  output logic [WIDTH-1:0]        o_rdata
);

`ifdef RAT_MEM_TSMC_N22
  // ── Compiled SRAM macro (TSMC N22) — replace with the real instance + pin map ──
  // TS1N22ULLSBLVTC256X32M4SWBASO u_macro (
  //   .CLK(clk), .CEB(~i_ce), .WEB(~i_we), .A(i_addr), .D(i_wdata), .Q(o_rdata));
`elsif RAT_MEM_SKY130
  // ── Compiled SRAM macro (SkyWater 130) ──
  // sky130_sram_1rw1r_... u_macro ( ... );
`else
  // ── Behavioral model — SIMULATION ONLY (skipped at synthesis) ──
  // synopsys translate_off
  logic [WIDTH-1:0] mem [0:DEPTH-1];
  always_ff @(posedge clk) begin
    if (i_ce) begin
      if (i_we) mem[i_addr] <= i_wdata;
      o_rdata <= mem[i_addr];  // 1-cycle read latency
    end
  end
  // synopsys translate_on
`endif

endmodule
