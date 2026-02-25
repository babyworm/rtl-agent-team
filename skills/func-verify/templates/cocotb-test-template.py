"""
cocotb Test Template for {{MODULE}}
Convention: dut.i_* (inputs), dut.o_* (outputs), dut.{{DOMAIN}}_clk, dut.{{DOMAIN}}_rst_n
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer


async def reset_dut(dut, duration_ns=100):
    """Apply reset: drive {{DOMAIN}}_rst_n low, wait, release."""
    dut.{{DOMAIN}}_rst_n.value = 0
    await Timer(duration_ns, units="ns")
    dut.{{DOMAIN}}_rst_n.value = 1
    await RisingEdge(dut.{{DOMAIN}}_clk)


@cocotb.test()
async def test_reset_behavior(dut):
    """Verify outputs are in known state after reset."""
    clock = Clock(dut.{{DOMAIN}}_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # Check reset state
    # assert dut.o_valid.value == 0, "o_valid should be 0 after reset"
    # assert dut.o_data.value == 0, "o_data should be 0 after reset"


@cocotb.test()
async def test_basic_operation(dut):
    """Verify basic input-to-output operation."""
    clock = Clock(dut.{{DOMAIN}}_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # Drive inputs
    # dut.i_data.value = 0xAB
    # dut.i_valid.value = 1
    # await RisingEdge(dut.{{DOMAIN}}_clk)

    # Wait for output
    # for _ in range(10):
    #     await RisingEdge(dut.{{DOMAIN}}_clk)
    #     if dut.o_valid.value == 1:
    #         break

    # Compare with reference model
    # expected = ref_model(0xAB)
    # assert dut.o_data.value == expected, \
    #     f"Mismatch: RTL={int(dut.o_data.value):#x}, ref={expected:#x}"


@cocotb.test()
async def test_backpressure(dut):
    """Verify correct behavior under backpressure (ready deasserted)."""
    clock = Clock(dut.{{DOMAIN}}_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # Hold ready low while driving valid
    # dut.i_valid.value = 1
    # dut.i_data.value = 0x42
    # dut.i_ready.value = 0
    # await ClockCycles(dut.{{DOMAIN}}_clk, 5)

    # Release ready
    # dut.i_ready.value = 1
    # await RisingEdge(dut.{{DOMAIN}}_clk)

    # Verify data was held correctly
    # assert dut.o_data.value == 0x42


@cocotb.test()
async def test_random_vectors(dut):
    """Run N random test vectors comparing RTL vs reference model."""
    import random
    random.seed(42)  # Deterministic for reproducibility

    clock = Clock(dut.{{DOMAIN}}_clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    num_vectors = 100
    mismatches = 0

    for i in range(num_vectors):
        test_val = random.randint(0, 2**8 - 1)  # Adjust width
        # dut.i_data.value = test_val
        # dut.i_valid.value = 1
        # await RisingEdge(dut.{{DOMAIN}}_clk)
        # ... wait for output ...
        # expected = ref_model(test_val)
        # if int(dut.o_data.value) != expected:
        #     mismatches += 1
        #     dut._log.error(f"Vector {i}: input={test_val:#x}, RTL={int(dut.o_data.value):#x}, ref={expected:#x}")

    assert mismatches == 0, f"{mismatches}/{num_vectors} vectors failed"
