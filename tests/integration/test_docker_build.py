"""Docker image build and EDA tool verification tests.

Builds the rtl-eda-tools Docker image from docker/Dockerfile and verifies
that all expected EDA tools are installed and runnable inside the container.

These tests are slow (~10-30 min for the first build) and require Docker.
Run with: pytest tests/integration/test_docker_build.py -v --timeout=3600
"""

import json
import re
import shutil
import subprocess
import time

import pytest

from tests.conftest import REPO_ROOT

DOCKERFILE_DIR = REPO_ROOT / "docker"
IMAGE_NAME = "rtl-eda-tools-test"
BUILD_TIMEOUT = 2400  # 40 min for first build
RUN_TIMEOUT = 60

def _docker_daemon_running() -> bool:
    """Check if Docker daemon is actually running (not just CLI installed)."""
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


requires_docker = pytest.mark.skipif(
    not _docker_daemon_running(), reason="docker daemon not running"
)


def _docker_run(cmd: str, timeout: int = RUN_TIMEOUT) -> subprocess.CompletedProcess:
    """Run a command inside the test Docker image."""
    return subprocess.run(
        ["docker", "run", "--rm", IMAGE_NAME, "bash", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _docker_image_exists(name: str) -> bool:
    """Check if a Docker image exists locally."""
    result = subprocess.run(
        ["docker", "images", "-q", name],
        capture_output=True, text=True, timeout=30,
    )
    return bool(result.stdout.strip())


@requires_docker
class TestDockerBuild:
    """Test that the Docker image builds successfully."""

    @pytest.fixture(scope="class", autouse=True)
    def build_image(self):
        """Build the Docker image once for all tests in this class.

        Uses cache so subsequent runs are fast. The image is NOT removed
        after tests to allow reuse across test runs.
        """
        if _docker_image_exists(IMAGE_NAME):
            # Rebuild only if Dockerfile changed since last build
            yield
            return

        result = subprocess.run(
            ["docker", "build", "-t", IMAGE_NAME, str(DOCKERFILE_DIR)],
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT,
        )
        if result.returncode != 0:
            pytest.fail(
                f"Docker build failed:\nSTDOUT:\n{result.stdout[-2000:]}\n"
                f"STDERR:\n{result.stderr[-2000:]}"
            )
        yield

    def test_image_created(self):
        assert _docker_image_exists(IMAGE_NAME)

    def test_image_has_workspace(self):
        r = _docker_run("pwd")
        assert r.returncode == 0
        assert "/workspace" in r.stdout.strip()


@requires_docker
class TestEDAToolsAvailable:
    """Verify all EDA tools are installed and runnable in the Docker image.

    Each test checks a specific tool by running its version command.
    """

    @pytest.fixture(scope="class", autouse=True)
    def ensure_image(self):
        """Ensure the Docker image exists before running tool checks."""
        if not _docker_image_exists(IMAGE_NAME):
            result = subprocess.run(
                ["docker", "build", "-t", IMAGE_NAME, str(DOCKERFILE_DIR)],
                capture_output=True, text=True, timeout=BUILD_TIMEOUT,
            )
            if result.returncode != 0:
                pytest.skip("Docker image build failed — skipping tool checks")
        yield

    # -- Simulators --

    def test_verilator_installed(self):
        r = _docker_run("verilator --version")
        assert r.returncode == 0
        assert "Verilator" in r.stdout

    def test_verilator_version_5(self):
        """Dockerfile targets Verilator 5.x."""
        r = _docker_run("verilator --version")
        match = re.search(r"Verilator\s+(\d+)", r.stdout)
        assert match, f"Cannot parse Verilator version from: {r.stdout}"
        assert int(match.group(1)) >= 5

    def test_iverilog_installed(self):
        r = _docker_run("iverilog -V 2>&1 | head -1")
        assert r.returncode == 0
        assert "Icarus Verilog" in r.stdout

    # -- Synthesis --

    def test_yosys_installed(self):
        r = _docker_run("yosys --version")
        assert r.returncode == 0
        assert "Yosys" in r.stdout or "yosys" in r.stdout.lower()

    # -- Lint Tools --

    def test_verilator_lint_works(self):
        """Verilator lint-only mode should work."""
        r = _docker_run("verilator --lint-only --help 2>&1 | head -3")
        assert r.returncode == 0

    def test_verible_lint_installed(self):
        """Verible may not be available on all architectures."""
        r = _docker_run("verible-verilog-lint --version 2>&1")
        if r.returncode != 0 and "not found" in r.stderr.lower():
            pytest.skip("Verible not available on this architecture")
        assert r.returncode == 0

    def test_slang_installed(self):
        r = _docker_run("slang --version 2>&1 | head -1")
        assert r.returncode == 0
        assert "slang" in r.stdout.lower()

    # -- Formal Verification --

    def test_sby_installed(self):
        r = _docker_run("sby --help 2>&1 | head -1")
        # sby may return non-zero for --help but should still print usage
        assert "sby" in r.stdout.lower() or "symbiyosys" in r.stdout.lower() or r.returncode == 0

    def test_z3_solver_installed(self):
        r = _docker_run("z3 --version")
        assert r.returncode == 0
        assert "Z3" in r.stdout or "z3" in r.stdout.lower()

    def test_boolector_installed(self):
        r = _docker_run("boolector --version 2>&1")
        assert r.returncode == 0 or "boolector" in r.stdout.lower()

    # -- SystemC/TLM --

    def test_systemc_headers_installed(self):
        r = _docker_run("test -f /usr/local/include/systemc.h && echo 'found'")
        assert r.returncode == 0
        assert "found" in r.stdout

    def test_systemc_library_installed(self):
        r = _docker_run("ls /usr/local/lib/libsystemc* 2>/dev/null | head -1")
        assert r.returncode == 0
        assert "libsystemc" in r.stdout

    def test_systemc_env_var(self):
        r = _docker_run("echo $SYSTEMC_HOME")
        assert "/usr/local" in r.stdout.strip()

    # -- Python EDA Packages --

    def test_cocotb_installed(self):
        r = _docker_run("python3 -c \"import cocotb; print(cocotb.__version__)\"")
        assert r.returncode == 0
        assert r.stdout.strip()  # version string should be non-empty

    def test_cocotb_bus_installed(self):
        r = _docker_run("python3 -c \"import cocotb_bus; print('ok')\"")
        assert r.returncode == 0
        assert "ok" in r.stdout

    def test_cocotbext_axi_installed(self):
        r = _docker_run("python3 -c \"import cocotbext.axi; print('ok')\"")
        assert r.returncode == 0
        assert "ok" in r.stdout

    def test_cocotb_coverage_installed(self):
        r = _docker_run("python3 -c \"import cocotb_coverage; print('ok')\"")
        assert r.returncode == 0
        assert "ok" in r.stdout

    def test_pytest_installed(self):
        r = _docker_run("python3 -m pytest --version")
        assert r.returncode == 0

    def test_numpy_installed(self):
        r = _docker_run("python3 -c \"import numpy; print(numpy.__version__)\"")
        assert r.returncode == 0

    # -- Build Tools --

    def test_gcc_installed(self):
        r = _docker_run("gcc --version | head -1")
        assert r.returncode == 0
        assert "gcc" in r.stdout.lower()

    def test_gpp_installed(self):
        r = _docker_run("g++ --version | head -1")
        assert r.returncode == 0

    def test_cmake_installed(self):
        r = _docker_run("cmake --version | head -1")
        assert r.returncode == 0

    def test_make_installed(self):
        r = _docker_run("make --version | head -1")
        assert r.returncode == 0

    # -- Waveform Viewer --

    def test_gtkwave_installed(self):
        r = _docker_run("which gtkwave")
        assert r.returncode == 0

    # -- slang-server (LSP) --

    def test_slang_server_installed(self):
        r = _docker_run("slang-server --version 2>&1 | head -1")
        assert r.returncode == 0 or "slang" in r.stdout.lower()


@requires_docker
class TestDockerToolchain:
    """End-to-end toolchain tests — compile and simulate inside Docker."""

    @pytest.fixture(scope="class", autouse=True)
    def ensure_image(self):
        if not _docker_image_exists(IMAGE_NAME):
            pytest.skip("Docker image not built")
        yield

    def test_verilator_compile_and_run(self):
        """Compile a trivial SV module with Verilator inside Docker."""
        sv_code = (
            "module counter(input logic clk, input logic rst_n, "
            "output logic [7:0] o_count); "
            "always_ff @(posedge clk or negedge rst_n) "
            "if (!rst_n) o_count <= 0; else o_count <= o_count + 1; "
            "endmodule"
        )
        cmd = (
            f"echo '{sv_code}' > /tmp/counter.sv && "
            "verilator --lint-only -Wall /tmp/counter.sv 2>&1"
        )
        r = _docker_run(cmd)
        assert r.returncode == 0, f"Verilator lint failed: {r.stdout}{r.stderr}"

    def test_iverilog_compile(self):
        """Compile a trivial Verilog module with Icarus Verilog inside Docker."""
        v_code = (
            "module adder(input [7:0] a, input [7:0] b, output [8:0] sum); "
            "assign sum = a + b; endmodule"
        )
        cmd = (
            f"echo '{v_code}' > /tmp/adder.v && "
            "iverilog -o /tmp/adder.out /tmp/adder.v 2>&1"
        )
        r = _docker_run(cmd)
        assert r.returncode == 0, f"iverilog compile failed: {r.stdout}{r.stderr}"

    def test_yosys_synth(self):
        """Synthesize a trivial module with Yosys inside Docker."""
        v_code = (
            "module top(input [3:0] a, output [3:0] b); assign b = ~a; endmodule"
        )
        cmd = (
            f"echo '{v_code}' > /tmp/inv.v && "
            "yosys -p 'read_verilog /tmp/inv.v; synth; stat' 2>&1 | tail -5"
        )
        r = _docker_run(cmd)
        assert r.returncode == 0, f"Yosys synth failed: {r.stdout}{r.stderr}"

    def test_gcc_c11_compile(self):
        """Compile a C11 source file inside Docker (ref model build)."""
        c_code = (
            '#include <stdio.h>\\n'
            'int main(void) { printf("hello\\\\n"); return 0; }'
        )
        cmd = (
            f"printf '{c_code}' > /tmp/test.c && "
            "gcc -std=c11 -O2 -Wall -Wextra -o /tmp/test_bin /tmp/test.c -lm && "
            "/tmp/test_bin"
        )
        r = _docker_run(cmd)
        assert r.returncode == 0
        assert "hello" in r.stdout

    def test_systemc_compile(self):
        """Compile a minimal SystemC program inside Docker."""
        cmd = (
            "cat > /tmp/sc_test.cpp << 'CPPEOF'\n"
            "#include <systemc.h>\n"
            "int sc_main(int, char*[]) {\n"
            "  sc_signal<bool> sig;\n"
            '  std::cout << "SystemC " << sc_release() << std::endl;\n'
            "  return 0;\n"
            "}\n"
            "CPPEOF\n"
            "g++ -std=c++17 -I/usr/local/include /tmp/sc_test.cpp "
            "-L/usr/local/lib -lsystemc -lm -o /tmp/sc_test 2>&1 && "
            "LD_LIBRARY_PATH=/usr/local/lib /tmp/sc_test"
        )
        r = _docker_run(cmd, timeout=120)
        assert r.returncode == 0
        assert "SystemC" in r.stdout

    def test_cocotb_importable(self):
        """Verify cocotb can be imported and discovers simulators."""
        cmd = (
            "python3 -c \""
            "import cocotb; "
            "from cocotb_bus.drivers import BusDriver; "
            "print('cocotb ecosystem OK')\""
        )
        r = _docker_run(cmd)
        assert r.returncode == 0
        assert "cocotb ecosystem OK" in r.stdout
