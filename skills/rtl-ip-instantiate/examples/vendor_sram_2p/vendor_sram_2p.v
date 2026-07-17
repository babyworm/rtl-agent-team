// vendor_sram_2p.v — Vendor two-port SRAM macro stub (256x32).
// Deliberately vendor-style: ALL-CAPS port names, no i_/o_ prefixes,
// active-low chip enables. Behavioral placeholder — in a real project this
// file is the vendor deliverable (do not edit; wrap it instead).

module vendor_sram_2p #(
    parameter W = 32,               // word width in bits
    parameter D = 256               // number of words
) (
    // Port A: write
    input                   CLKA,
    input                   CENA,   // chip enable, active-low
    input  [$clog2(D)-1:0]  AA,
    input  [W-1:0]          DA,

    // Port B: read
    input                   CLKB,
    input                   CENB,   // chip enable, active-low
    input  [$clog2(D)-1:0]  AB,
    output reg [W-1:0]      QB,

    // Margin / test controls
    input  [2:0]            EMA,    // read margin adjustment
    input                   RET1N,  // retention mode, active-low
    input                   STOV    // self-time override
);

    reg [W-1:0] mem [0:D-1];

    always @(posedge CLKA) begin
        if (!CENA) mem[AA] <= DA;
    end

    always @(posedge CLKB) begin
        if (!CENB) QB <= mem[AB];
    end

    // Margin/test pins have no behavioral effect in this stub.
    wire unused_ok = &{1'b0, EMA, RET1N, STOV};

endmodule
