"""
Example: AXI-Lite Register Read/Write Test using cocotbext-axi
Convention: dut.sys_clk, dut.sys_rst_n, dut.i_*/o_* (slave perspective)
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotbext.axi import AxiLiteMaster, AxiLiteBus


async def reset_dut(dut, duration_ns=100):
    """Apply reset sequence."""
    dut.sys_rst_n.value = 0
    await Timer(duration_ns, units="ns")
    dut.sys_rst_n.value = 1
    await RisingEdge(dut.sys_clk)
    await RisingEdge(dut.sys_clk)


@cocotb.test()
async def test_register_write_read(dut):
    """Write a value to a register, read it back, verify match."""
    clock = Clock(dut.sys_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # Create AXI-Lite master BFM
    # Note: AxiLiteBus.from_prefix maps s_axi -> i_s_axi_*/o_s_axi_* signals
    axi_master = AxiLiteMaster(
        AxiLiteBus.from_prefix(dut, "s_axi"),
        dut.sys_clk,
        dut.sys_rst_n,
        reset_active_level=False  # Active-low reset
    )

    # Write 0xDEADBEEF to address 0x00
    await axi_master.write(0x00, b'\xef\xbe\xad\xde')

    # Read back from address 0x00
    data = await axi_master.read(0x00, 4)

    assert data.data == b'\xef\xbe\xad\xde', \
        f"Read mismatch: got {data.data.hex()}, expected deadbeef"


@cocotb.test()
async def test_multiple_registers(dut):
    """Write different values to multiple registers, verify all."""
    clock = Clock(dut.sys_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    axi_master = AxiLiteMaster(
        AxiLiteBus.from_prefix(dut, "s_axi"),
        dut.sys_clk,
        dut.sys_rst_n,
        reset_active_level=False
    )

    test_data = {
        0x00: 0x12345678,
        0x04: 0xAABBCCDD,
        0x08: 0x00FF00FF,
        0x0C: 0xCAFEBABE,
    }

    # Write all registers
    for addr, val in test_data.items():
        await axi_master.write(addr, val.to_bytes(4, 'little'))

    # Read and verify all registers
    for addr, expected in test_data.items():
        data = await axi_master.read(addr, 4)
        actual = int.from_bytes(data.data, 'little')
        assert actual == expected, \
            f"Addr {addr:#x}: got {actual:#010x}, expected {expected:#010x}"
