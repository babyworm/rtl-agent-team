// Standard SRAM Wrapper — Dual-Port (DP)
// Deploy to: rtl/common/dpreg.sv and rtl/common/wrapper/dpreg_<depth>_<width>.sv 
// Separate read and write ports, DUAL clock (`wclk`/`rclk`). Use at clock domain
// crossings (e.g., async FIFO memory backend, cross-domain shared buffer).
// Instance naming: `u_mem_{purpose}`.
// For synthesis, add the sram_sp-style `ifdef compiled-macro branches above the
// behavioral block; the behavioral body stays translate_off-guarded.
// Note: two always_ff blocks writing different signals (`mem` from wclk,
// `o_rdata` from rclk) is correct — each signal has a single driver.
module dpreg #(
  parameter int DEPTH = 256,
  parameter int WIDTH = 32
) (
  // Write port (write clock domain)
  input  logic                    wclk,
  input  logic                    i_wen,
  input  logic [$clog2(DEPTH)-1:0] i_waddr,
  input  logic [WIDTH-1:0]        i_wdata,
  // Read port (read clock domain)
  input  logic                    rclk,
  input  logic                    i_ren,
  input  logic [$clog2(DEPTH)-1:0] i_raddr,
  output logic [WIDTH-1:0]        o_rdata
);

// To use ASIC compiled memory 
`ifdef ASIC_SYNTHESIS
  `ifdef RAT_MEM_TSMC_N22
     // ── Compiled SRAM macro (TSMC N22) — replace with the real instance + pin map ──
     // 
  `elsif RAT_MEM_SKY130
    // ── Compiled SRAM macro (SkyWater 130) ──
    // sky130_sram_1rw1r_... u_macro ( ... );
  `else
  $warning("compiled memory is not instanced while synthesis");
  `endif 


// To use behavioral model  
`else // end of ASIC_SYNTHESIS
  
  // Behavioral model — SIMULATION ONLY 
  // synopsys translate_off
  logic [WIDTH-1:0] mem [0:DEPTH-1];

  always_ff @(posedge wclk) begin
    if (i_wen) begin
      mem[i_waddr] <= i_wdata;
    end
  end

  always_ff @(posedge rclk) begin
    if (i_ren) begin
      o_rdata <= mem[i_raddr];  // 1-cycle read latency (rclk domain)
    end
  end
  // synopsys translate_on
`endif // !ASIC_SYNTHESIS
endmodule
