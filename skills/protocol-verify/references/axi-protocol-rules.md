# AXI Protocol Verification Rules Reference

## AXI4 Handshake Rules (AMBA AXI Specification)

### Rule 1: VALID must not depend on READY
- xVALID MUST NOT wait for xREADY to be asserted before asserting
- xREADY CAN wait for xVALID before asserting (but doesn't have to)
- This applies to ALL five channels: AW, W, B, AR, R

### Rule 2: VALID must remain asserted until handshake
- Once xVALID is asserted, it MUST remain asserted until xREADY is also asserted
- The handshake occurs on the clock edge where both VALID and READY are high

### Rule 3: Data/control must be stable while VALID is high
- All signals on a channel MUST remain stable while xVALID is high and xREADY is low
- Changing data while waiting for READY is a protocol violation

## AXI4 Channel-Specific Rules

### Write Address Channel (AW)
```systemverilog
// AWVALID must not depend on AWREADY
ap_aw_valid_no_ready_dep: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  $rose(i_awvalid) |-> i_awvalid throughout (o_awready[->1])
);

// AWADDR must be stable while AWVALID && !AWREADY
ap_aw_addr_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_awvalid && !o_awready) |=> $stable(i_awaddr)
);
```

### Write Data Channel (W)
```systemverilog
// WVALID stability
ap_w_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_wvalid && !o_wready) |=> i_wvalid
);

// WDATA stability
ap_w_data_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_wvalid && !o_wready) |=> $stable(i_wdata)
);

// WLAST must be asserted for last beat of burst
ap_w_last_on_final: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_wvalid && o_wready && i_wlast) |-> ##1 (!i_wvalid || $rose(i_awvalid))
);
```

### Write Response Channel (B)
```systemverilog
// BVALID stability
ap_b_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (o_bvalid && !i_bready) |=> o_bvalid
);

// BRESP stability
ap_b_resp_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (o_bvalid && !i_bready) |=> $stable(o_bresp)
);
```

### Read Address Channel (AR)
```systemverilog
// Same pattern as AW channel
ap_ar_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_arvalid && !o_arready) |=> i_arvalid
);
```

### Read Data Channel (R)
```systemverilog
// RVALID stability
ap_r_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (o_rvalid && !i_rready) |=> o_rvalid
);

// RLAST must be asserted for last beat
ap_r_last_count: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (o_rvalid && i_rready && o_rlast) |-> ##1 (!o_rvalid || $rose(i_arvalid))
);
```

## AXI4 Ordering Rules

| Rule | Description |
|------|-------------|
| Write ordering | Write response (B) MUST NOT be issued before last write data (W with WLAST) |
| Read ordering | Read data MUST be returned in the order of the address request (per ID) |
| Write-Read ordering | No ordering requirement between reads and writes (unless same ID in AXI3) |
| Outstanding transactions | Multiple requests can be outstanding; responses can be interleaved by ID |

## AXI4-Lite Restrictions (vs Full AXI4)

| Feature | AXI4 | AXI4-Lite |
|---------|------|-----------|
| Burst length | 1-256 | Always 1 (no bursts) |
| Data width | 8-1024 bits | 32 or 64 bits only |
| WSTRB | Optional | Required for writes |
| Exclusive access | Supported | NOT supported |
| Cache/Prot | Full support | Simplified |
| ID signals | Required | NOT present |

## Common AXI Violations Found in Practice

1. **WVALID before AWVALID**: Master sends write data before write address — violates ordering
2. **VALID drops without handshake**: VALID deasserted before READY acknowledged — data loss
3. **Data changes during wait**: Signal values change while VALID high and READY low — corruption
4. **Missing WLAST**: Burst write never asserts WLAST — slave cannot determine burst end
5. **Response before data**: BVALID asserted before all WDATA received — premature response
6. **RDATA after RLAST**: Extra read data beats after RLAST — protocol error
