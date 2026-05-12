# axi_stream_bridge

> Auto-generated from `tests/fixtures/rtl-document/axi_stream_bridge.sv`. Replace every `<!-- LLM_FILL: ... -->` marker.

## Overview

Asynchronous bridge from APB-controlled `sys` domain to an AXI4-Stream egress on `pixel` domain, using two async FIFOs.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| DATA_WIDTH | int | 64 | Width of the AXI4-Stream data path in bits. |

## Ports

| Port Name | Direction | Width | Clock Domain | Kind | Description |
|-----------|-----------|-------|--------------|------|-------------|
| sys_clk | input | 1 | sys | clock | |
| sys_rst_n | input | 1 | sys | reset | |
| pixel_clk | input | 1 | pixel | clock | |
| pixel_rst_n | input | 1 | pixel | reset | |
| i_psel | input | 1 | ? | data | APB control (sys domain) — selects this peripheral. |
| i_penable | input | 1 | ? | data | APB control (sys domain) — qualifies the access phase. |
| i_paddr | input | 1 | ? | data | APB control (sys domain) — 32-bit register address. |
| o_tdata | output | DATA_WIDTH | ? | data | AXI4-Stream egress (pixel domain) — output data. |
| o_tvalid | output | 1 | ? | data | AXI4-Stream egress (pixel domain) — data valid. |
| i_tready | input | 1 | ? | data | AXI4-Stream egress (pixel domain) — downstream ready. |

## Clock Domains

| Domain | Clock | Reset | Usage |
|--------|-------|-------|-------|
| pixel | pixel_clk | pixel_rst_n | AXI4-Stream egress domain; drives `o_tdata`, `o_tvalid`, `i_tready` and the egress FIFO read side. |
| sys | sys_clk | sys_rst_n | APB control domain; drives `i_psel`, `i_penable`, `i_paddr` and the ingress FIFO write side. |

## Sub-Module Instances

| Instance | Module | Purpose |
|----------|--------|---------|
| u_ingress_fifo | async_fifo | Asynchronous FIFO clocked write-side in `sys` domain, read-side in `pixel` domain. |
| u_egress_fifo | async_fifo | Asynchronous FIFO providing additional buffering on the AXI4-Stream egress path. |

## Block Diagram

```d2
# axi_stream_bridge sub-instances
  u_ingress_fifo: async_fifo
  u_egress_fifo: async_fifo

```

## Design Notes

Both async FIFOs are instantiated with `#(.WIDTH(DATA_WIDTH))` and connected via `(.*)`, so all port connections rely on implicit port matching. Ensure `async_fifo` port names align exactly with `axi_stream_bridge` signals to avoid unintended port mismatches during elaboration.
