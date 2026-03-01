# cocotb Ecosystem Reference

## Core cocotb (2.0+)

### Key Imports
```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, Timer, with_timeout
from cocotb.regression import TestFactory
```

### Async Patterns (cocotb 2.0)
```python
@cocotb.test()
async def test_basic(dut):
    # Start clock
    clock = Clock(dut.sys_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut.sys_rst_n.value = 0
    await ClockCycles(dut.sys_clk, 5)
    dut.sys_rst_n.value = 1
    await RisingEdge(dut.sys_clk)

    # Drive and check
    dut.i_data.value = 0xDEAD
    dut.i_valid.value = 1
    await RisingEdge(dut.sys_clk)

    # Timeout protection
    async with with_timeout(ClockCycles(dut.sys_clk, 100), timeout_unit="ns", timeout_time=1000):
        while dut.o_valid.value != 1:
            await RisingEdge(dut.sys_clk)
```

### Test Factory (Parameterized Tests)
```python
from cocotb.regression import TestFactory

async def run_test(dut, data_width=8, burst_len=1):
    """Parameterized test template"""
    pass

factory = TestFactory(run_test)
factory.add_option("data_width", [8, 16, 32])
factory.add_option("burst_len", [1, 4, 16])
factory.generate_tests()
# Generates: run_test_0008_0001, run_test_0008_0004, ... (9 tests total)
```

## cocotb-bus: Driver/Monitor Framework

```bash
pip install cocotb-bus
```

### Driver Base Class
```python
from cocotb_bus.drivers import BusDriver

class MyDriver(BusDriver):
    _signals = ["i_data", "i_valid", "o_ready"]

    async def _driver_send(self, transaction, sync=True):
        if sync:
            await RisingEdge(self.clock)
        self.bus.i_data.value = transaction["data"]
        self.bus.i_valid.value = 1
        while True:
            await RisingEdge(self.clock)
            if self.bus.o_ready.value:
                break
        self.bus.i_valid.value = 0
```

### Monitor Base Class
```python
from cocotb_bus.monitors import BusMonitor

class MyMonitor(BusMonitor):
    _signals = ["o_data", "o_valid", "i_ready"]

    async def _monitor_recv(self):
        while True:
            await RisingEdge(self.clock)
            if self.bus.o_valid.value and self.bus.i_ready.value:
                self._recv(int(self.bus.o_data.value))
```

### Scoreboard
```python
from cocotb_bus.scoreboard import Scoreboard

scoreboard = Scoreboard(dut)
scoreboard.add_interface(monitor, expected_output_list)
# At end: scoreboard.result  # raises TestFailure if mismatch
```

## cocotbext-axi: AXI Bus Functional Models

```bash
pip install cocotbext-axi
```

### AXI4-Lite Master
```python
from cocotbext.axi import AxiLiteMaster, AxiLiteBus

axi_master = AxiLiteMaster(
    AxiLiteBus.from_prefix(dut, "s_axi"),
    dut.sys_clk,
    dut.sys_rst_n,
    reset_active_level=False
)

# Write register
await axi_master.write(0x0000, b'\x01\x02\x03\x04')

# Read register
data = await axi_master.read(0x0000, 4)
assert data.data == b'\x01\x02\x03\x04'
```

### AXI4-Stream
```python
from cocotbext.axi import AxiStreamSource, AxiStreamSink, AxiStreamBus, AxiStreamFrame

source = AxiStreamSource(
    AxiStreamBus.from_prefix(dut, "s_axis"),
    dut.sys_clk, dut.sys_rst_n, reset_active_level=False
)
sink = AxiStreamSink(
    AxiStreamBus.from_prefix(dut, "m_axis"),
    dut.sys_clk, dut.sys_rst_n, reset_active_level=False
)

# Send frame
frame = AxiStreamFrame(tdata=b'\x01\x02\x03\x04', tuser=0)
await source.send(frame)

# Receive frame
rx_frame = await sink.recv()
assert rx_frame.tdata == b'\x01\x02\x03\x04'
```

### AXI4 Full Master
```python
from cocotbext.axi import AxiMaster, AxiBus

axi_master = AxiMaster(
    AxiBus.from_prefix(dut, "s_axi"),
    dut.sys_clk, dut.sys_rst_n, reset_active_level=False
)

# Burst write (INCR, 4 beats)
await axi_master.write(0x1000, b'\x00' * 64)

# Burst read
data = await axi_master.read(0x1000, 64)
```

## cocotb-coverage: Functional Coverage

```bash
pip install cocotb-coverage
```

```python
from cocotb_coverage.coverage import CoverPoint, CoverCross, coverage_db, CoverCheck

# Define coverage points
@CoverPoint("top.data_range",
    xf=lambda data: data,
    bins=[range(0, 64), range(64, 128), range(128, 192), range(192, 256)])
@CoverPoint("top.protocol_state",
    xf=lambda data, valid, ready: (valid, ready),
    bins=[(1, 1), (1, 0), (0, 1)])
@CoverCross("top.data_x_protocol",
    items=["top.data_range", "top.protocol_state"])
def sample(data, valid=0, ready=0):
    pass

# In test: call sample() on every transaction
sample(int(dut.o_data.value), int(dut.o_valid.value), int(dut.i_ready.value))

# At end: check coverage
coverage_db.report_coverage(cocotb.log.info, bins=True)
assert coverage_db["top"].coverage >= 90.0, "Coverage below 90%"
```

## Simulator Backends

| Simulator | Make Command | Pros | Cons | Role |
|-----------|-------------|------|------|------|
| Verilator | `make SIM=verilator EXTRA_ARGS="--trace-fst --timing"` | Fastest simulation, FST traces, good coverage | Stricter SV subset, 2-state only | **Default** |
| Icarus Verilog | `make SIM=icarus` | 4-state X/Z, delay modeling, good SV support | Slower simulation | **Fallback** (X/Z, delays, unsupported constructs) |
| ModelSim/Questa | `make SIM=modelsim` | Full IEEE 1800, UVM | Commercial license | Commercial |
| VCS | `make SIM=vcs` | Fastest, full IEEE 1800 | Commercial license | Commercial |

## Useful Environment Variables

```bash
COCOTB_RESOLVE_X=RANDOM    # Resolve X to random 0/1 (useful for reset handling)
COCOTB_LOG_LEVEL=DEBUG      # Verbose logging
RANDOM_SEED=42              # Reproducible random tests
WAVES=1                     # Enable waveform dumping
```
