"""Shared pytest fixtures for rtl-agent-team plugin tests."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ── Project root ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
HOOKS_DIR = REPO_ROOT / "hooks"
SKILLS_DIR = REPO_ROOT / "skills"


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with .rat/state/."""
    state_dir = tmp_path / ".rat" / "state"
    state_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def tmp_legacy_project(tmp_path):
    """Create a project with only .rtl-agent-team (no .rat) -- legacy layout."""
    state_dir = tmp_path / ".rtl-agent-team" / "state"
    state_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def sample_sv_clean(tmp_path):
    """Create a clean SV file that passes all convention checks."""
    sv = tmp_path / "good_module.sv"
    sv.write_text("""\
module good_module (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [7:0]  i_data,
  output logic [7:0]  o_result
);

  logic [7:0] r_data;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      r_data <= 8'd0;
    else
      r_data <= i_data;
  end

  assign o_result = r_data;

endmodule
""")
    return sv


@pytest.fixture
def yosys_stat_output():
    """Sample Yosys stat output for parse_yosys_stat tests."""
    return """\
=== design hierarchy ===

   top_module              1

=== top_module ===

   Number of wires:                 42
   Number of wire bits:            256
   Number of memories:               0
   Number of memory bits:            0

   Statistics:
     $_DFF_P_                       16
     $_DFF_PN1_                      8
     $add                            4
     $mux                           12
     $not                            2

   Chip area for module 'top_module': 33.516000
"""


@pytest.fixture
def yosys_stat_with_latches():
    """Sample Yosys stat output with inferred latches."""
    return """\
=== design hierarchy ===

   top_module              1

=== top_module ===

   Number of wires:                 10
   Number of wire bits:             64

   Statistics:
     $_DFF_P_                        4
     $_DLATCH_P_                     2
     $mux                            3
"""


@pytest.fixture
def yosys_stat_empty():
    """Sample Yosys stat output with no cells (empty design)."""
    return """\
=== design hierarchy ===

   top_module              1

=== top_module ===

   Number of wires:                  0
   Number of wire bits:              0

   Statistics:
"""


@pytest.fixture
def encoder_output_hm_style():
    """Sample HM-style encoder output for parse_encoder_output tests."""
    return (
        "POC    0 TId: 0 ( I-SLICE, nQP 32 )\n"
        "Bitrate      1234.56 kbps\n"
        "PSNR-Y  36.4500\n"
        "PSNR-U  40.1200\n"
        "PSNR-V  41.3400\n"
        "PSNR-YUV  37.2100\n"
        "Total encoding time: 5.678s\n"
    )


@pytest.fixture
def rd_results_sample(tmp_path):
    """Create a sample results.json for BD-rate calculation."""
    results = [
        {"sequence": "BasketballDrill", "qp": 22, "config_label": "anchor",
         "bitrate_kbps": 4096.0, "psnr_y": 42.5, "psnr_u": 44.0, "psnr_v": 44.5,
         "psnr_yuv": 42.5, "encode_time_s": 10.0, "status": "success", "is_anchor": True},
        {"sequence": "BasketballDrill", "qp": 27, "config_label": "anchor",
         "bitrate_kbps": 2048.0, "psnr_y": 39.9, "psnr_u": 42.0, "psnr_v": 42.5,
         "psnr_yuv": 39.9, "encode_time_s": 8.0, "status": "success", "is_anchor": True},
        {"sequence": "BasketballDrill", "qp": 32, "config_label": "anchor",
         "bitrate_kbps": 1024.0, "psnr_y": 36.8, "psnr_u": 39.0, "psnr_v": 39.5,
         "psnr_yuv": 36.8, "encode_time_s": 6.0, "status": "success", "is_anchor": True},
        {"sequence": "BasketballDrill", "qp": 37, "config_label": "anchor",
         "bitrate_kbps": 512.0, "psnr_y": 33.5, "psnr_u": 36.0, "psnr_v": 36.5,
         "psnr_yuv": 33.5, "encode_time_s": 4.0, "status": "success", "is_anchor": True},
        {"sequence": "BasketballDrill", "qp": 22, "config_label": "test",
         "bitrate_kbps": 3840.0, "psnr_y": 42.7, "psnr_u": 44.2, "psnr_v": 44.7,
         "psnr_yuv": 42.7, "encode_time_s": 12.0, "status": "success", "is_anchor": False},
        {"sequence": "BasketballDrill", "qp": 27, "config_label": "test",
         "bitrate_kbps": 1920.0, "psnr_y": 40.1, "psnr_u": 42.2, "psnr_v": 42.7,
         "psnr_yuv": 40.1, "encode_time_s": 10.0, "status": "success", "is_anchor": False},
        {"sequence": "BasketballDrill", "qp": 32, "config_label": "test",
         "bitrate_kbps": 960.0, "psnr_y": 37.0, "psnr_u": 39.2, "psnr_v": 39.7,
         "psnr_yuv": 37.0, "encode_time_s": 8.0, "status": "success", "is_anchor": False},
        {"sequence": "BasketballDrill", "qp": 37, "config_label": "test",
         "bitrate_kbps": 480.0, "psnr_y": 33.7, "psnr_u": 36.2, "psnr_v": 36.7,
         "psnr_yuv": 33.7, "encode_time_s": 6.0, "status": "success", "is_anchor": False},
    ]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results, indent=2))
    return path


# ── Shared text extraction helper ────────────────────────────────────────────

def extract_marked_block(path: Path, start_marker: str, end_marker: str) -> str:
    """Extract lines between start_marker and end_marker (exclusive) from path."""
    lines = path.read_text().splitlines()
    in_block = False
    out = []

    for line in lines:
        if line == start_marker:
            in_block = True
            continue
        if in_block and line == end_marker:
            return "\n".join(out).strip()
        if in_block:
            out.append(line)

    raise AssertionError(f"Markers not found in {path}: {start_marker} ... {end_marker}")


# ── Helper to run shell scripts ───────────────────────────────────────────────

def run_script(script_path, *args, stdin_data=None, env=None, cwd=None, timeout=30):
    """Run a shell script and return CompletedProcess."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(script_path), *args],
        capture_output=True,
        text=True,
        input=stdin_data,
        env=merged_env,
        cwd=cwd,
        timeout=timeout,
    )


def run_hook(hook_path, stdin_json, cwd=None, timeout=10, env=None):
    """Run a hook script with JSON on stdin, return parsed JSON output."""
    if isinstance(stdin_json, dict):
        stdin_json = json.dumps(stdin_json)
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        ["sh", str(hook_path)],
        capture_output=True,
        text=True,
        input=stdin_json,
        env=merged_env,
        cwd=cwd,
        timeout=timeout,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": result.stdout, "stderr": result.stderr, "rc": result.returncode}
