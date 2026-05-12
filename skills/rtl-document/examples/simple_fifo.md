# simple_fifo

> Auto-generated from `tests/fixtures/rtl-document/simple_fifo.sv`. Replace every `<!-- LLM_FILL: ... -->` marker.

## Overview

Synchronous FIFO with `DATA_WIDTH`-bit data path and `DEPTH` entries, providing single-cycle push/pop with full/empty flags.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| DATA_WIDTH | int | 32 | Width of the data path in bits. |
| DEPTH | int | 16 | Number of storage entries in the FIFO. |

## Ports

| Port Name | Direction | Width | Clock Domain | Kind | Description |
|-----------|-----------|-------|--------------|------|-------------|
| sys_clk | input | 1 | sys | clock | |
| sys_rst_n | input | 1 | sys | reset | |
| i_push | input | 1 | ? | data | |
| i_data | input | DATA_WIDTH | ? | data | Write data word, sampled when `i_push` is asserted. |
| i_pop | input | 1 | ? | data | |
| o_data | output | DATA_WIDTH | ? | data | Read data word presented at the head of the FIFO. |
| o_full | output | 1 | ? | data | |
| o_empty | output | 1 | ? | data | |

## Clock Domains

| Domain | Clock | Reset | Usage |
|--------|-------|-------|-------|
| sys | sys_clk | sys_rst_n | Single synchronous domain clocking all FIFO logic and memory array. |

## Synthesis Summary

- Area: **12450.30 um^2**
- WNS: **0.210 ns**
- TNS: **-3.400 ns**

## Design Notes

TNS of −3.400 ns with 2 violating paths indicates the memory array read path may be timing-critical at the default `DEPTH`=16 / `DATA_WIDTH`=32 configuration; verify timing constraints match the target frequency before tapeout.
