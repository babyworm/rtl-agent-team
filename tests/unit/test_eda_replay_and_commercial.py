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
        replay = outdir / "scr" / "replay" / "run_syn_dc_shell_latest.sh"
        assert replay.exists()
        assert "dc_shell -64bit -f" in replay.read_text()
        # Multicore host option is emitted into the generated DC Tcl (default 8)
        scr_files = list((outdir / "scr").glob("dc_syn_m_*.tcl"))
        assert scr_files, "DC Tcl script was not generated"
        assert "set_host_options -max_cores 8" in scr_files[0].read_text()

    def test_dc_shell_max_cores_override(self, tmp_path):
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
            "--max-cores",
            "4",
            "--outdir",
            str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode == 0
        scr_files = list((outdir / "scr").glob("dc_syn_m_*.tcl"))
        assert scr_files, "DC Tcl script was not generated"
        assert "set_host_options -max_cores 4" in scr_files[0].read_text()

    def test_dc_shell_rejects_invalid_max_cores(self, tmp_path):
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
            "--max-cores",
            "abc",
            "--outdir",
            str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            timeout=20,
        )
        assert result.returncode != 0
        assert "max-cores" in (result.stderr or "")

    def test_genus_synth_emits_multicore_host_option(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        outdir = tmp_path / "syn_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "genus", "echo GENUS_FAKE \"$@\"")

        result = run_script(
            RUN_SYN,
            "--tool",
            "genus",
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
        scr_files = list((outdir / "scr").glob("genus_syn_m_*.tcl"))
        assert scr_files, "Genus Tcl script was not generated"
        assert "set_db max_cpus_per_server 8" in scr_files[0].read_text()

    def test_ppa_compile_fragment_sets_host_options(self):
        # PPA path bypasses run_syn.sh auto-gen, so the compile fragment itself
        # must enable multicore before compile_ultra.
        frag = (
            SKILLS_DIR
            / "ppa-optimizer-dc-policy"
            / "templates"
            / "dc-compile-ppa.tcl"
        )
        text = frag.read_text()
        assert "set_host_options -max_cores" in text
        # set_host_options must precede the compile_ultra COMMAND to take effect.
        # Match command lines only (comments may also mention "compile_ultra").
        cmd_lines = [ln.strip() for ln in text.splitlines()]
        sho_idx = next(
            i for i, ln in enumerate(cmd_lines) if ln.startswith("set_host_options")
        )
        cu_idx = next(
            i for i, ln in enumerate(cmd_lines) if ln.startswith("compile_ultra")
        )
        assert sho_idx < cu_idx

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


# ── Memory-wrapper blackbox / compiler-macro handling (run_syn.sh) ──────────
# Blackbox/warning/strict are emitted INTO the generated Tcl, gated on get_cells finding
# real (instantiated) memory cells — so tests assert on generated-Tcl content (the fake
# tool does not execute the Tcl). This is instantiation-aware (Codex R1: declaration ≠
# instantiation), so a declared-but-unused wrapper never false-fails --mem-strict.
_SRAM_SP = """\
module sram_sp #(parameter int DEPTH = 256, WIDTH = 32) (
  input  logic                     clk, i_ce, i_we,
  input  logic [$clog2(DEPTH)-1:0] i_addr,
  input  logic [WIDTH-1:0]         i_wdata,
  output logic [WIDTH-1:0]         o_rdata
);
`ifdef RAT_MEM_TSMC_N22
  // TS1N22ULL u_macro (.CLK(clk), .CEB(~i_ce), .WEB(~i_we), .A(i_addr), .D(i_wdata), .Q(o_rdata));
`else
  // synopsys translate_off
  logic [WIDTH-1:0] mem [0:DEPTH-1];
  always_ff @(posedge clk) if (i_ce) begin
    if (i_we) mem[i_addr] <= i_wdata;
    o_rdata <= mem[i_addr];
  end
  // synopsys translate_on
`endif
endmodule
"""


def _mem_fixture(tmp_path, tool):
    """Top instantiating sram_sp + the wrapper + filelist + fake tool."""
    (tmp_path / "m.sv").write_text(
        "module m(input logic clk);\n"
        "  logic [31:0] q;\n"
        "  sram_sp u_mem_x (.clk(clk), .i_ce(1'b1), .i_we(1'b0),\n"
        "    .i_addr('0), .i_wdata('0), .o_rdata(q));\n"
        "endmodule\n"
    )
    (tmp_path / "sram_sp.sv").write_text(_SRAM_SP)
    flist = tmp_path / "f.f"
    flist.write_text(f"{tmp_path / 'sram_sp.sv'}\n{tmp_path / 'm.sv'}\n")
    outdir = tmp_path / "syn_out"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    binname = "dc_shell" if tool == "dc_shell" else "genus"
    _make_fake_tool(fake_bin, binname, f'echo {binname.upper()}_FAKE "$@"')
    return flist, outdir, fake_bin


def _gen_script(outdir, prefix):
    files = list((outdir / "scr").glob(f"{prefix}_m_*.tcl"))
    assert files, f"{prefix} Tcl not generated"
    return files[0].read_text()


class TestMemoryBlackbox:
    def _run(self, flist, outdir, fake_bin, tool, *extra):
        return run_script(
            RUN_SYN, "--tool", tool, "--top", "m", "-f", str(flist),
            "--outdir", str(outdir), *extra,
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"}, timeout=20,
        )

    def test_dc_blackbox_block_when_no_mem_lib(self, tmp_path):
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(flist, outdir, fake_bin, "dc_shell")
        assert result.returncode == 0
        tcl = _gen_script(outdir, "dc_syn")
        # instantiation-aware blackbox, gated on get_cells finding real cells
        assert "get_cells -quiet -hierarchical -filter {ref_name =~ sram_sp*" in tcl
        assert "set_dont_touch" in tcl and "set_disable_timing" in tcl
        # warning lives in the generated Tcl (printed by the tool), not shell stderr
        assert "blackboxed" in tcl
        assert "blackboxed" not in result.stderr

    def test_dc_macro_active_with_mem_lib(self, tmp_path):
        memlib = tmp_path / "tsmc.db"
        memlib.write_text("// fake db\n")
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(
            flist, outdir, fake_bin, "dc_shell",
            "--mem-process", "RAT_MEM_TSMC_N22", "--mem-lib", str(memlib),
        )
        assert result.returncode == 0
        tcl = _gen_script(outdir, "dc_syn")
        assert "-define {RAT_MEM_TSMC_N22}" in tcl
        assert "set_disable_timing" not in tcl       # macro linked → not blackboxed
        assert "get_cells -quiet -hierarchical" not in tcl
        setup = (outdir / "scr" / ".synopsys_dc.setup").read_text()
        assert str(memlib) in setup                  # linked into link_library

    def test_dc_mem_strict_emits_error_in_tcl(self, tmp_path):
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(flist, outdir, fake_bin, "dc_shell", "--mem-strict")
        assert result.returncode == 0   # enforced at synthesis (real tool), not pre-launch
        tcl = _gen_script(outdir, "dc_syn")
        assert "--mem-strict" in tcl and "exit 1" in tcl

    def test_strict_no_false_fail_when_declared_but_unused(self, tmp_path):
        # sram_sp.sv IS in the filelist but the top does NOT instantiate it. Under --mem-strict
        # this must NOT shell-fail (Codex R1-F1 / R2-F3): strict lives in the generated Tcl,
        # gated on get_cells finding real (elaborated) cells — declaration alone never fails.
        (tmp_path / "sram_sp.sv").write_text(_SRAM_SP)
        (tmp_path / "m.sv").write_text("module m(input logic clk); endmodule\n")  # no instance
        flist = tmp_path / "f.f"
        flist.write_text(f"{tmp_path / 'sram_sp.sv'}\n{tmp_path / 'm.sv'}\n")
        outdir = tmp_path / "syn_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')
        result = self._run(flist, outdir, fake_bin, "dc_shell", "--mem-strict")
        assert result.returncode == 0
        assert "blackboxed" not in result.stderr  # no shell-side warning at all
        tcl = _gen_script(outdir, "dc_syn")        # strict lives in the Tcl, gated on get_cells
        assert "exit 1" in tcl and "get_cells" in tcl

    def test_dc_lib_without_process_is_blackboxed(self, tmp_path):
        # --mem-lib alone does NOT activate the wrapper's `ifdef macro branch (that needs
        # --mem-process), so the wrapper stays the empty translate_off `else → must still be
        # blackboxed (Codex R2-F1).
        memlib = tmp_path / "tsmc.db"
        memlib.write_text("// fake db\n")
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(flist, outdir, fake_bin, "dc_shell", "--mem-lib", str(memlib))
        assert result.returncode == 0
        tcl = _gen_script(outdir, "dc_syn")
        assert "get_cells -quiet -hierarchical -filter {ref_name =~ sram_sp*" in tcl
        assert "set_disable_timing" in tcl  # blackboxed despite --mem-lib (no --mem-process)

    def test_dc_process_only_is_blackboxed(self, tmp_path):
        # --mem-process without --mem-lib → macro unresolved → blackbox (4th MEM_BLACKBOX combo).
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(flist, outdir, fake_bin, "dc_shell", "--mem-process", "RAT_MEM_TSMC_N22")
        assert result.returncode == 0
        tcl = _gen_script(outdir, "dc_syn")
        assert "-define {RAT_MEM_TSMC_N22}" in tcl       # branch activated
        assert "get_cells -quiet -hierarchical" in tcl   # but blackboxed (no lib)
        assert "set_disable_timing" in tcl

    def test_genus_blackbox_block(self, tmp_path):
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "genus")
        result = self._run(flist, outdir, fake_bin, "genus")
        assert result.returncode == 0
        tcl = _gen_script(outdir, "genus_syn")
        assert "set_dont_touch" in tcl and "set_disable_timing" in tcl
        assert "blackboxed" in tcl

    def test_genus_macro_active_with_both_flags(self, tmp_path):
        memlib = tmp_path / "tsmc.db"
        memlib.write_text("// fake db\n")
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "genus")
        result = self._run(
            flist, outdir, fake_bin, "genus",
            "--mem-process", "RAT_MEM_TSMC_N22", "--mem-lib", str(memlib),
        )
        assert result.returncode == 0
        tcl = _gen_script(outdir, "genus_syn")
        assert "-define {RAT_MEM_TSMC_N22}" in tcl
        assert "set_disable_timing" not in tcl           # macro active → not blackboxed
        assert str(memlib) in tcl                        # linked in set_db library

    def test_genus_lib_without_process_is_blackboxed(self, tmp_path):
        memlib = tmp_path / "tsmc.db"
        memlib.write_text("// fake db\n")
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "genus")
        result = self._run(flist, outdir, fake_bin, "genus", "--mem-lib", str(memlib))
        assert result.returncode == 0
        tcl = _gen_script(outdir, "genus_syn")
        assert "set_disable_timing" in tcl               # blackboxed (no --mem-process)

    def test_genus_process_only_is_blackboxed(self, tmp_path):
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "genus")
        result = self._run(flist, outdir, fake_bin, "genus", "--mem-process", "RAT_MEM_TSMC_N22")
        assert result.returncode == 0
        tcl = _gen_script(outdir, "genus_syn")
        assert "-define {RAT_MEM_TSMC_N22}" in tcl
        assert "set_disable_timing" in tcl   # blackboxed (no --mem-lib)

    def test_mem_module_rejects_non_identifier(self, tmp_path):
        # A glob-bearing/blank --mem-module token must be rejected — never become
        # `ref_name =~ *` (which would blackbox the whole design). Codex R3-F1.
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(flist, outdir, fake_bin, "dc_shell", "--mem-module", "bad*name")
        assert result.returncode != 0
        assert "mem-module" in result.stderr

    def test_mem_lib_rejects_tcl_metachars(self, tmp_path):
        # --mem-lib is emitted into Tcl double quotes; a path with Tcl-active chars must be
        # rejected so it cannot trigger command substitution at synthesis. Codex R4-F1.
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = self._run(
            flist, outdir, fake_bin, "dc_shell",
            "--mem-process", "RAT_MEM_X", "--mem-lib", "/libs/macro[exec].db",
        )
        assert result.returncode != 0
        assert "mem-lib" in result.stderr

    def test_source_path_with_tcl_metachars_rejected(self, tmp_path):
        # Every emitted path (incl. source files) must be Tcl-safe (Codex R6-F1).
        d = tmp_path / "wo[rk]"
        d.mkdir()
        (d / "m.sv").write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(d / "m.sv") + "\n")
        outdir = tmp_path / "syn_out"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')
        result = self._run(flist, outdir, fake_bin, "dc_shell")
        assert result.returncode != 0
        assert "Tcl-unsafe" in result.stderr

    def test_top_rejects_non_identifier(self, tmp_path):
        # --top is emitted into Tcl (`elaborate $TOP`); a non-identifier must be rejected.
        flist, outdir, fake_bin = _mem_fixture(tmp_path, "dc_shell")
        result = run_script(
            RUN_SYN, "--tool", "dc_shell", "--top", "m[0]", "-f", str(flist),
            "--outdir", str(outdir),
            env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"}, timeout=20,
        )
        assert result.returncode != 0
        assert "top must be" in result.stderr
