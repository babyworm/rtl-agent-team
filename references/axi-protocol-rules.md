# AXI Protocol Rules and SVA Assertion Templates

> This document is the detailed reference for the `protocol-verify` skill.
> For core rules, see `<Steps>` in `skills/protocol-verify/SKILL.md`.

## 1. AXI4 Channel Overview

| Channel | Direction (Master→Slave) | Purpose |
|---------|--------------------------|---------|
| AW (Write Address) | M → S | Write address + burst info |
| W (Write Data) | M → S | Write data + strobe |
| B (Write Response) | S → M | Write response |
| AR (Read Address) | M → S | Read address + burst info |
| R (Read Data) | S → M | Read data + response |

All channels use **VALID/READY handshake**.

## 2. AXI4 Protocol Rules (per AMBA Spec)

### 2.1 Handshake Rules (Common to All Channels)

| Rule ID | Rule | SVA Pattern |
|---------|------|-------------|
| A3.2.1 | VALID can be asserted without READY | — (not a constraint) |
| A3.2.2 | VALID must hold after assertion until READY | `valid && !ready \|=> valid` |
| A3.2.1 | READY can be asserted without VALID | — (not a constraint) |
| — | Payload stable while VALID | `valid && !ready \|=> $stable(payload)` |

### 2.2 Write Address Channel (AW)

| Signal (Project Convention) | Direction | Description |
|-----------------------------|-----------|-------------|
| `i_awaddr` | M→S | Write start address |
| `i_awlen` | M→S | Burst length (beats - 1) |
| `i_awsize` | M→S | Bit/byte size (log2) |
| `i_awburst` | M→S | Burst type (FIXED/INCR/WRAP) |
| `i_awvalid` | M→S | Address valid |
| `o_awready` | S→M | Address accepted |

### 2.3 Write Data Channel (W)

| Signal | Direction | Description |
|--------|-----------|-------------|
| `i_wdata` | M→S | Write data |
| `i_wstrb` | M→S | Byte strobe |
| `i_wlast` | M→S | Last beat |
| `i_wvalid` | M→S | Data valid |
| `o_wready` | S→M | Data accepted |

### 2.4 Write Response Channel (B)

| Signal | Direction | Description |
|--------|-----------|-------------|
| `o_bresp` | S→M | Response (OKAY/SLVERR/DECERR) |
| `o_bvalid` | S→M | Response valid |
| `i_bready` | M→S | Response accepted |

### 2.5 Read Address Channel (AR)

| Signal | Direction | Description |
|--------|-----------|-------------|
| `i_araddr` | M→S | Read start address |
| `i_arlen` | M→S | Burst length |
| `i_arsize` | M→S | Bit/byte size |
| `i_arburst` | M→S | Burst type |
| `i_arvalid` | M→S | Address valid |
| `o_arready` | S→M | Address accepted |

### 2.6 Read Data Channel (R)

| Signal | Direction | Description |
|--------|-----------|-------------|
| `o_rdata` | S→M | Read data |
| `o_rresp` | S→M | Response |
| `o_rlast` | S→M | Last beat |
| `o_rvalid` | S→M | Data valid |
| `i_rready` | M→S | Data accepted |

## 3. SVA Assertion Templates per Channel

### 3.1 AW Channel

```systemverilog
// AWVALID holds until AWREADY
a_aw_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid && !o_awready |=> i_awvalid
) else $error("[%m] AWVALID dropped before AWREADY");

// AWADDR stable while waiting
a_aw_addr_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid && !o_awready |=> $stable(i_awaddr)
) else $error("[%m] AWADDR changed while AWVALID && !AWREADY");

// AWLEN stable
a_aw_len_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid && !o_awready |=> $stable(i_awlen)
) else $error("[%m] AWLEN changed");

// AWBURST valid (00=FIXED, 01=INCR, 10=WRAP, 11=reserved)
a_aw_burst_valid: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid |-> (i_awburst != 2'b11)
) else $error("[%m] AWBURST reserved value");
```

### 3.2 W Channel

```systemverilog
// WVALID holds
a_w_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> i_wvalid
) else $error("[%m] WVALID dropped");

// WDATA stable
a_w_data_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> $stable(i_wdata)
) else $error("[%m] WDATA changed");

// WSTRB stable
a_w_strb_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> $stable(i_wstrb)
) else $error("[%m] WSTRB changed");

// WLAST stable
a_w_last_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> $stable(i_wlast)
) else $error("[%m] WLAST changed");
```

### 3.3 B Channel

```systemverilog
// BVALID holds
a_b_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_bvalid && !i_bready |=> o_bvalid
) else $error("[%m] BVALID dropped");

// BRESP stable
a_b_resp_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_bvalid && !i_bready |=> $stable(o_bresp)
) else $error("[%m] BRESP changed");

// BRESP valid (00=OKAY, 01=EXOKAY, 10=SLVERR, 11=DECERR)
a_b_resp_valid: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_bvalid |-> (o_bresp inside {2'b00, 2'b01, 2'b10, 2'b11})
) else $error("[%m] BRESP invalid");
```

### 3.4 AR Channel

```systemverilog
a_ar_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_arvalid && !o_arready |=> i_arvalid
) else $error("[%m] ARVALID dropped");

a_ar_addr_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_arvalid && !o_arready |=> $stable(i_araddr)
) else $error("[%m] ARADDR changed");
```

### 3.5 R Channel

```systemverilog
a_r_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_rvalid && !i_rready |=> o_rvalid
) else $error("[%m] RVALID dropped");

a_r_data_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_rvalid && !i_rready |=> $stable(o_rdata)
) else $error("[%m] RDATA changed");

a_r_last_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_rvalid && !i_rready |=> $stable(o_rlast)
) else $error("[%m] RLAST changed");
```

## 4. AXI4-Lite Differences

AXI4-Lite is a simplified version of AXI4:

| Item | AXI4 | AXI4-Lite |
|------|------|-----------|
| Burst | AWLEN/ARLEN supported | Single transfer only (len=0) |
| Data width | Configurable | 32 or 64 bit |
| WSTRB | Fully supported | Fully supported |
| WLAST | Required | Not required (always 1) |
| ID | Supported | Not supported |
| SIZE | Supported | Fixed to data width |

## 5. Burst Type Rules

| Type | AxBURST | Behavior | Constraint |
|------|---------|----------|------------|
| FIXED | 2'b00 | Same address repeated | len ≤ 15 |
| INCR | 2'b01 | Address incrementing | len ≤ 255 |
| WRAP | 2'b10 | Address wrapping | len ∈ {1,3,7,15}, aligned |

## 6. Response Codes

| Code | RESP | Meaning |
|------|------|---------|
| OKAY | 2'b00 | Normal completion |
| EXOKAY | 2'b01 | Exclusive access success |
| SLVERR | 2'b10 | Slave error |
| DECERR | 2'b11 | Decode error (address out of range) |

## 7. APB Protocol Rules

APB (Advanced Peripheral Bus) is for simple register access:

| Signal | Direction | Description |
|--------|-----------|-------------|
| `i_psel` | M→S | Slave select |
| `i_penable` | M→S | Transfer enable |
| `i_pwrite` | M→S | Write(1)/Read(0) |
| `i_paddr` | M→S | Address |
| `i_pwdata` | M→S | Write data |
| `o_prdata` | S→M | Read data |
| `o_pready` | S→M | Transfer complete |
| `o_pslverr` | S→M | Error response |

APB protocol 2-phase: SETUP (psel=1, penable=0) → ACCESS (psel=1, penable=1, wait pready).
