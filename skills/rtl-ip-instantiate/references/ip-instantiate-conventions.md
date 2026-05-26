# IP Instantiation Conventions

A quick reference for `rtl-ip-instantiate`. Stays under 150 lines so it can be
consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Wrapper file | `rtl/ip_wrappers/{ip_name}_wrapper.sv` | `rtl/ip_wrappers/sram_wrapper.sv` |
| Wrapper module name | `{ip_name}_wrapper` | `sram_wrapper` |
| IP instance | `u_{ip_name}` (always `u_` prefix) | `u_sram` |
| Generate blocks | `gen_` prefix | `gen_data_width` |
| Input ports | `i_` prefix | `i_sram_din`, `i_addr` |
| Output ports | `o_` prefix | `o_sram_dout`, `o_valid` |
| Inout ports | `io_` prefix | `io_data_bus` |
| Clock | `clk` (single domain) or `{domain}_clk` | `sys_clk`, `pixel_clk` |
| Reset | `rst_n` (single domain) or `{domain}_rst_n` (active-low async) | `sys_rst_n` |
| Type keyword | `logic` only — never `reg` or `wire` | `logic [7:0] i_data` |
| Tied-off ports | `// TIED: <reason>` comment inline | `// TIED: unused test mode` |
| Parameter mapping | `// PARAM: <description>` comment inline | `// PARAM: data bus width` |

## 2. Output schema

### Wrapper module skeleton
```systemverilog
module sram_wrapper #(
    parameter DATA_WIDTH = 32  // PARAM: data bus width
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [DATA_WIDTH-1:0] i_sram_din,
    output logic [DATA_WIDTH-1:0] o_sram_dout
);
    // Internal signals
    logic [DATA_WIDTH-1:0] data_q;

    sram #(
        .WIDTH(DATA_WIDTH)
    ) u_sram (
        .clk   (clk),
        .rst_n (rst_n),
        .din   (i_sram_din),
        .dout  (o_sram_dout),
        .tm    (1'b0)   // TIED: unused test mode
    );
endmodule
```

### Vendor-to-project port name mapping pattern
| Vendor convention | Project convention |
|-------------------|--------------------|
| `clk_i` / `CLK` | `clk` or `{domain}_clk` |
| `rst_ni` / `RSTN` | `rst_n` or `{domain}_rst_n` |
| `data_i`, `din_i` | `i_{signal}` |
| `data_o`, `dout_o` | `o_{signal}` |
| `data_io` | `io_{signal}` |

## 3. Length / fidelity guidance

- Every IP port must appear in the instantiation — either connected to a wrapper port
  or tied off with a `// TIED: reason` comment. No silent unconnected ports.
- Parameter comments (`// PARAM: ...`) must describe purpose, not restate the name.
- Lint must pass (Verible + slang) before the wrapper is delivered. Fix all errors;
  do not suppress warnings without documenting rationale.
- Multi-domain wrappers: list each clock domain in a header comment block at the
  top of the module with its source and frequency (if known).

## 4. Anti-patterns

- Using `reg` or `wire` — `logic` only; `reg`/`wire` are not needed in IEEE 1800-2009 SV.
- Suffix convention (`data_i`, `clk_i`) — project uses prefix (`i_data`, `clk`).
- Leaving ports unconnected without a `// TIED:` comment — silent dangling ports
  cause simulation mismatches and mask synthesis warnings.
- Auto-resolving port width mismatches — always flag to the user; never silently truncate.
- Writing the wrapper without first reading existing `rtl/ip_wrappers/` conventions —
  inconsistent naming breaks downstream integration scripts.
