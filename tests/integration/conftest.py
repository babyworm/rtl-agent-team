"""Integration test fixtures — require EDA tools (Docker environment)."""

import shutil
import subprocess

import pytest


def _tool_available(name):
    """Check if an EDA tool is available on PATH."""
    return shutil.which(name) is not None


requires_iverilog = pytest.mark.skipif(
    not _tool_available("iverilog"), reason="iverilog not installed"
)
requires_verilator = pytest.mark.skipif(
    not _tool_available("verilator"), reason="verilator not installed"
)
requires_yosys = pytest.mark.skipif(
    not _tool_available("yosys"), reason="yosys not installed"
)
requires_verible = pytest.mark.skipif(
    not _tool_available("verible-verilog-lint"), reason="verible not installed"
)
requires_slang = pytest.mark.skipif(
    not _tool_available("slang"), reason="slang not installed"
)
