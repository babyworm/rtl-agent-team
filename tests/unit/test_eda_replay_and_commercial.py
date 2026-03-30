"""Tests for replay artifacts and commercial EDA wrapper paths."""

import os
from pathlib import Path

from tests.conftest import SCRIPTS_DIR, SKILLS_DIR, run_script

RUN_SIM = SCRIPTS_DIR / "run_sim.sh"
RUN_LINT = SKILLS_DIR / "rat-init-project" / "templates" / "run_lint.sh"
RUN_SYN = SKILLS_DIR / "rat-init-project" / "templates" / "run_syn.sh"
RUN_CDC = SKILLS_DIR / "rat-init-project" / "templates" / "run_cdc.sh"


def _make_fake_tool(bin_dir: Path, name: str, body: str) -> Path:
    tool = bin_dir / name
    tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n")
    tool.chmod(0o755)
    return tool


class TestRunSimReplay:
    def test_compile_generates_replay_scripts(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule\n")
        outdir = tmp_path / "sim_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()

        _make_fake_tool(
            fake_bin,
            "iverilog",
            "out=''; while [ $# -gt 0 ]; do if [ \"$1\" = '-o' ]; then out=\"$2\"; shift 2; continue; fi; shift; done; [ -n \"$out\" ] && : > \"$out\"",
        )

        result = run_script(
            RUN_SIM,
            "--sim",
            "iverilog",
            "--top",
            "dummy",
            "--compile-only",
            "--outdir",
            str(outdir),
            str(sv),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode == 0
        replay_dir = outdir / "replay"
        assert (replay_dir / "run_iverilog_compile_latest.sh").exists()
        assert (replay_dir / "run_iverilog_replay_latest.sh").exists()
        assert "iverilog -g2012" in (replay_dir / "run_iverilog_compile_latest.sh").read_text()

    def test_xcelium_alias_routes_to_xrun_and_replay(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule\n")
        outdir = tmp_path / "sim_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "xrun", "echo XRUN_FAKE \"$@\"")

        result = run_script(
            RUN_SIM,
            "--sim",
            "xcelium",
            "--top",
            "dummy",
            "--run-only",
            "--outdir",
            str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode == 0
        replay_run = outdir / "replay" / "run_xrun_run_latest.sh"
        assert replay_run.exists()
        assert "xrun -R" in replay_run.read_text()


class TestCommercialLintSynthCdcWrappers:
    def test_spyglass_lint_path_and_replay(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        outdir = tmp_path / "lint_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "sg_shell", "echo SG_SHELL_FAKE \"$@\"")

        result = run_script(
            RUN_LINT,
            "--tool",
            "spyglass",
            "--top",
            "m",
            "-f",
            str(flist),
            "--outdir",
            str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode == 0
        replay = outdir / "replay" / "run_lint_spyglass_latest.sh"
        assert replay.exists()
        assert "sg_shell -tcl" in replay.read_text()

    def test_dc_shell_synth_path_and_replay(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        outdir = tmp_path / "syn_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "dc_shell", "echo DC_FAKE \"$@\"")

        result = run_script(
            RUN_SYN,
            "--tool",
            "dc_shell",
            "--top",
            "m",
            "-f",
            str(flist),
            "--outdir",
            str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode == 0
        replay = outdir / "replay" / "run_syn_dc_shell_latest.sh"
        assert replay.exists()
        assert "dc_shell -64bit -f" in replay.read_text()

    def test_spyglass_cdc_path_and_replay(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m(input logic sys_clk, input logic axi_clk); endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        outdir = tmp_path / "cdc_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "sg_shell", "echo SG_SHELL_CDC_FAKE \"$@\"")

        result = run_script(
            RUN_CDC,
            "--tool",
            "spyglass",
            "--top",
            "m",
            "-f",
            str(flist),
            "--outdir",
            str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode == 0
        replay = outdir / "replay" / "run_cdc_spyglass_latest.sh"
        assert replay.exists()
        assert "sg_shell -tcl" in replay.read_text()
