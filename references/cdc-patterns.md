# CDC (Clock Domain Crossing) Patterns and Constraints

> This document is the detailed reference for the `cdc-verify` skill.
> For core rules, see `<Steps>` in `skills/cdc-verify/SKILL.md`.

## 1. Synchronizer Types

### 1.1 2-FF Synchronizer (Single Bit)

The most basic CDC pattern. For single-bit signals only.

```systemverilog
module sync_2ff #(
  parameter int unsigned STAGES = 2
) (
  input  logic dst_clk,
  input  logic dst_rst_n,
  input  logic i_async,
  output logic o_sync
);
  logic [STAGES-1:0] sync_q;

  always_ff @(posedge dst_clk or negedge dst_rst_n) begin
    if (!dst_rst_n)
      sync_q <= '0;
    else
      sync_q <= {sync_q[STAGES-2:0], i_async};
  end

  assign o_sync = sync_q[STAGES-1];
endmodule
```

**Usage**: Single-bit control signals (enable, flag, interrupt)

### 1.2 Gray Code FIFO (Multi-bit Bus)

Multi-bit data is transferred via a gray code FIFO.

```systemverilog
// Gray code conversion
function automatic logic [W-1:0] bin2gray(input logic [W-1:0] bin);
  return bin ^ (bin >> 1);
endfunction

function automatic logic [W-1:0] gray2bin(input logic [W-1:0] gray);
  logic [W-1:0] bin;
  bin[W-1] = gray[W-1];
  for (int i = W-2; i >= 0; i--)
    bin[i] = bin[i+1] ^ gray[i];
  return bin;
endfunction
```

**Structure**:
```
Writer (src_clk) → FIFO RAM → Reader (dst_clk)
  wr_ptr (binary) → bin2gray → 2-FF sync → gray2bin → wr_ptr_sync
  rd_ptr (binary) → bin2gray → 2-FF sync → gray2bin → rd_ptr_sync
```

**Usage**: Multi-bit data streams, CDC requiring buffering

### 1.3 Pulse Synchronizer

Transfers a 1-cycle pulse from the source domain to the destination domain.

```systemverilog
module sync_pulse (
  input  logic src_clk,
  input  logic src_rst_n,
  input  logic dst_clk,
  input  logic dst_rst_n,
  input  logic i_pulse,
  output logic o_pulse
);
  logic toggle_q;
  logic [1:0] sync_q;

  // Source: toggle on pulse
  always_ff @(posedge src_clk or negedge src_rst_n) begin
    if (!src_rst_n) toggle_q <= 1'b0;
    else if (i_pulse) toggle_q <= ~toggle_q;
  end

  // Destination: 2-FF sync + edge detect
  always_ff @(posedge dst_clk or negedge dst_rst_n) begin
    if (!dst_rst_n) sync_q <= 2'b0;
    else sync_q <= {sync_q[0], toggle_q};
  end

  assign o_pulse = sync_q[1] ^ sync_q[0];
endmodule
```

**Usage**: Interrupts, event notifications

### 1.4 Handshake Synchronizer

Safely transfers data + valid. Bidirectional handshake.

```
src_clk domain:          dst_clk domain:
  req ─── 2-FF sync ───► req_sync
  ack ◄── 2-FF sync ──── ack
  data ─────────────────► data (stable while req high)
```

**Usage**: Slow control paths, register configuration value transfers

## 2. Common CDC Violations

| Violation | Description | Severity | Fix |
|-----------|-------------|----------|-----|
| Multi-bit bus crossing | Directly syncing multiple bits | Critical | Use gray code FIFO |
| Missing synchronizer | No sync on CDC path | Critical | Add 2-FF sync |
| Reconvergence | CDC signal diverges then reconverges | High | Distribute after single sync |
| Glitch on MUX select | CDC signal controls MUX | High | Sync before MUX select |
| Reset domain crossing | Async reset in different domain | Medium | Add reset sync |
| FIFO pointer sync | Directly syncing binary pointer | Critical | Gray code required |
| Pulse too narrow | src pulse < dst period | High | Use pulse sync |

## 3. SDC Constraint Templates for CDC

### 3.1 Asynchronous Clock Groups

```tcl
# Unrelated clock domains
set_clock_groups -asynchronous \
  -group [get_clocks sys_clk] \
  -group [get_clocks pixel_clk]
```

### 3.2 Individual False Paths

```tcl
# 2-FF synchronizer path
set_false_path -from [get_clocks sys_clk] \
  -to [get_pins u_sync_*/sync_q_reg[0]/D]

# Gray code FIFO pointer path
set_false_path -from [get_clocks sys_clk] \
  -to [get_pins u_async_fifo/rd_ptr_gray_sync_reg[*][0]/D]
```

### 3.3 Max Delay (optional)

```tcl
# Set max_delay on synchronizer path (skew limitation)
set_max_delay -datapath_only \
  -from [get_clocks sys_clk] -to [get_pins u_sync_*/sync_q_reg[0]/D] \
  [expr {$dst_period * 0.8}]
```

## 4. CDC Verification Checklist

| Item | Verification Method | Tool |
|------|---------------------|------|
| Synchronizer on all CDC paths | Structural check | CDC tool / grep |
| Gray code for multi-bit bus | Code review | Manual / CDC tool |
| No reconvergence | Path tracing | CDC tool |
| SDC false_path settings | SDC review | Synthesis tool |
| Reset synchronizer present | Code review | Manual |
| Pulse width >= dst period | Timing analysis | Simulation |

## 5. CDC Verification Tools

| Tool | Type | Usage |
|------|------|-------|
| Verilator | Structural check (limited) | `--lint-only -Wall` |
| Slang | Structural check | `--lint-only` |
| CDC formal (commercial) | Mathematical proof | Cadence JasperGold CDC, Synopsys VC CDC |
| Simulation | Dynamic verification | Multi-clock testbench |

In open-source environments, combine structural checks (grep + lint) with simulation-based CDC verification.
