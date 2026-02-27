# cocotb Ecosystem Reference

> This document is the detailed reference for the `func-verify` skill.
> For core rules, see `<Steps>` in `skills/func-verify/SKILL.md`.

## 1. cocotb Core API

### 1.1 Coroutine & Trigger

```python
import cocotb
from cocotb.triggers import (
    Timer, RisingEdge, FallingEdge, ClockCycles,
    Event, Combine, First, with_timeout
)

@cocotb.test()
async def my_test(dut):
    # Time-based
    await Timer(10, units="ns")

    # Edge-based (project rule: dut.sys_clk, NOT dut.clk_i)
    await RisingEdge(dut.sys_clk)
    await FallingEdge(dut.sys_rst_n)

    # Wait N cycles
    await ClockCycles(dut.sys_clk, 10)

    # Timeout
    await with_timeout(RisingEdge(dut.o_done), timeout_time=1, timeout_unit="us")

    # First of multiple events
    trigger = await First(
        RisingEdge(dut.o_done),
        Timer(100, units="us")
    )
```

### 1.2 Signal Access

```python
# Project rule: i_/o_ prefix, sys_clk/sys_rst_n
# NOT: dut.clk_i, dut.data_i

# Write
dut.i_data.value = 0xFF
dut.i_valid.value = 1

# Read
val = dut.o_result.value
val_int = dut.o_result.value.integer
val_bin = dut.o_result.value.binstr

# Assert
assert dut.o_valid.value == 1, "output not valid"

# Multi-bit
dut.i_data.value = 0xDEADBEEF  # integer
dut.i_data.value = BinaryValue("10101010")  # binary string
```

### 1.3 Clock Generation

```python
from cocotb.clock import Clock

# Generate 10ns period (100MHz) clock
clock = Clock(dut.sys_clk, 10, units="ns")
cocotb.start_soon(clock.start())
```

### 1.4 Reset Sequence

```python
async def reset_dut(dut, duration_ns=50):
    """Standard reset sequence (project convention: sys_rst_n, active-low)"""
    dut.sys_rst_n.value = 0
    await Timer(duration_ns, units="ns")
    dut.sys_rst_n.value = 1
    await RisingEdge(dut.sys_clk)
    await RisingEdge(dut.sys_clk)
```

## 2. cocotb-bus (Bus Protocol Drivers)

### 2.1 Installation

```bash
pip install cocotb-bus
```

### 2.2 AXI-Lite Master

```python
from cocotb_bus.drivers import BusDriver
from cocotb.triggers import RisingEdge

class AXILiteMaster:
    """AXI-Lite master for register access.
    Port naming follows project convention: i_/o_ prefix.
    """
    def __init__(self, dut, clk, rst_n, prefix=""):
        self.dut = dut
        self.clk = clk
        self.rst_n = rst_n
        self.prefix = prefix

    async def write(self, addr, data):
        """AXI-Lite write transaction."""
        # AW channel
        self.dut.i_awaddr.value = addr
        self.dut.i_awvalid.value = 1
        # W channel
        self.dut.i_wdata.value = data
        self.dut.i_wstrb.value = 0xF
        self.dut.i_wvalid.value = 1

        await RisingEdge(self.clk)
        while not self.dut.o_awready.value:
            await RisingEdge(self.clk)
        self.dut.i_awvalid.value = 0

        while not self.dut.o_wready.value:
            await RisingEdge(self.clk)
        self.dut.i_wvalid.value = 0

        # B channel
        self.dut.i_bready.value = 1
        while not self.dut.o_bvalid.value:
            await RisingEdge(self.clk)
        resp = self.dut.o_bresp.value
        self.dut.i_bready.value = 0
        return resp

    async def read(self, addr):
        """AXI-Lite read transaction."""
        self.dut.i_araddr.value = addr
        self.dut.i_arvalid.value = 1

        await RisingEdge(self.clk)
        while not self.dut.o_arready.value:
            await RisingEdge(self.clk)
        self.dut.i_arvalid.value = 0

        self.dut.i_rready.value = 1
        while not self.dut.o_rvalid.value:
            await RisingEdge(self.clk)
        data = self.dut.o_rdata.value.integer
        resp = self.dut.o_rresp.value
        self.dut.i_rready.value = 0
        return data, resp
```

## 3. cocotb-coverage (Functional Coverage)

### 3.1 Installation

```bash
pip install cocotb-coverage
```

### 3.2 CoverPoint & CoverCross

```python
from cocotb_coverage.coverage import (
    CoverPoint, CoverCross, coverage_db, CoverCheck
)

# CoverPoint definition
@CoverPoint("top.cmd", xf=lambda dut: dut.i_cmd.value.integer,
            bins=[0, 1, 2, 3])
@CoverPoint("top.size", xf=lambda dut: dut.i_size.value.integer,
            bins=[1, 2, 4, 8])
@CoverCross("top.cmd_x_size",
            items=["top.cmd", "top.size"])
def sample_coverage(dut):
    """Sample coverage after each transaction."""
    pass

# Usage in test
@cocotb.test()
async def test_coverage(dut):
    for _ in range(100):
        # ... drive stimulus ...
        sample_coverage(dut)

    # Coverage report
    coverage_db.report_coverage(cocotb.log.info, bins=True)
    coverage_db.export_to_xml("coverage.xml")
```

### 3.3 Coverage Goal Check

```python
# Check specific goal achievement
for cp_name, cp in coverage_db.items():
    pct = cp.cover_percentage
    cocotb.log.info(f"{cp_name}: {pct:.1f}%")
    assert pct >= 90.0, f"Coverage goal not met: {cp_name} = {pct:.1f}%"
```

## 4. Makefile Template

```makefile
# cocotb Makefile (project standard)
TOPLEVEL_LANG = verilog
SIM           ?= icarus

# Source files (project convention: _pkg first)
VERILOG_SOURCES = \
    $(PWD)/../../rtl/include/my_module_pkg.sv \
    $(PWD)/../../rtl/src/my_module.sv

# Top module
TOPLEVEL = my_module

# Test module (Python)
MODULE = test_my_module

# cocotb options
export COCOTB_REDUCED_LOG_FMT = 1

# Verilator-specific
ifeq ($(SIM),verilator)
    EXTRA_ARGS += --trace --trace-fst
    EXTRA_ARGS += -Wno-fatal
endif

# Icarus-specific
ifeq ($(SIM),icarus)
    COMPILE_ARGS += -g2012
    PLUSARGS += +DUMP_WAVES=1
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
```

## 5. Waveform Dump

```python
# VCD dump (Icarus)
# In Makefile: PLUSARGS += +DUMP_WAVES=1
# Icarus automatically generates dump.vcd

# FST dump (Verilator)
# In Makefile: EXTRA_ARGS += --trace --trace-fst
# Generates dump.fst in build directory

# View with gtkwave
# gtkwave dump.vcd &
# gtkwave dump.fst &
```

## 6. Reference Model Integration

```python
import ctypes

# Load C reference model
lib = ctypes.CDLL("./ref_model/build/libref_model.so")
lib.ref_compute.restype = ctypes.c_uint32
lib.ref_compute.argtypes = [ctypes.c_uint32]

@cocotb.test()
async def test_vs_ref(dut):
    """Compare DUT output with reference model."""
    for i in range(100):
        input_val = random.randint(0, 0xFFFFFFFF)
        dut.i_data.value = input_val
        dut.i_valid.value = 1
        await RisingEdge(dut.sys_clk)
        dut.i_valid.value = 0

        # Wait for result
        while not dut.o_valid.value:
            await RisingEdge(dut.sys_clk)

        # Compare
        expected = lib.ref_compute(input_val)
        actual = dut.o_result.value.integer
        assert actual == expected, \
            f"Mismatch: input={input_val:#x} expected={expected:#x} got={actual:#x}"
```

## 7. Project Rules Summary (cocotb)

| Item | Correct Usage | Prohibited |
|------|---------------|------------|
| Clock | `dut.sys_clk`, `dut.clk` | `dut.clk_i` |
| Reset | `dut.sys_rst_n`, `dut.rst_n` | `dut.rst_ni` |
| Input | `dut.i_data`, `dut.i_valid` | `dut.data_i`, `dut.data_in` |
| Output | `dut.o_result`, `dut.o_ready` | `dut.result_o`, `dut.data_out` |
