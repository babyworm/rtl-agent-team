"""Contract tests for synthesis runner filelist and tool-option handling."""

import os
from pathlib import Path

from tests.conftest import SKILLS_DIR, run_script

RUN_SYN = SKILLS_DIR / "rat-init-project" / "templates" / "run_syn.sh"


def _make_fake_tool(bin_dir: Path, name: str, body: str) -> Path:
    bin_dir.mkdir(exist_ok=True)
    tool = bin_dir / name
    tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n")
    tool.chmod(0o755)
    return tool


def _env(fake_bin: Path) -> dict[str, str]:
    return {"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"}


def _write_filelist_project(project: Path) -> Path:
    (project / "rtl" / "include").mkdir(parents=True)
    (project / "rtl" / "common").mkdir(parents=True)
    (project / "rtl" / "common" / "helper.sv").write_text("module helper; endmodule\n")
    (project / "rtl" / "leaf.sv").write_text("module leaf; endmodule\n")
    (project / "rtl" / "top.sv").write_text("module top; leaf u_leaf(); endmodule\n")
    (project / "rtl" / "nested.f").write_text("rtl/leaf.sv\n")
    top_f = project / "rtl" / "top.f"
    top_f.write_text(
        "+incdir+rtl/include\n"
        "+define+FEATURE=1\n"
        "-f rtl/nested.f\n"
        "rtl/common/helper.sv\n"
        "rtl/top.sv\n"
    )
    return top_f


def test_filelist_options_reach_dc_generated_script(tmp_path: Path) -> None:
    flist = _write_filelist_project(tmp_path)
    outdir = tmp_path / "syn_out"
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')

    result = run_script(
        RUN_SYN,
        "--tool",
        "dc_shell",
        "--top",
        "top",
        "-f",
        str(flist),
        "--outdir",
        str(outdir),
        env=_env(fake_bin),
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    script = next((outdir / "scr").glob("dc_syn_top_*.tcl")).read_text()
    setup = (outdir / "scr" / ".synopsys_dc.setup").read_text()
    assert f"set_app_var search_path [concat [get_app_var search_path] [list {tmp_path / 'rtl' / 'include'}]]" in setup
    assert f'analyze -format sverilog -define {{FEATURE=1}} "{tmp_path / "rtl" / "common" / "helper.sv"}"' in script
    assert f'analyze -format sverilog -define {{FEATURE=1}} "{tmp_path / "rtl" / "leaf.sv"}"' in script
    assert script.count(str(tmp_path / "rtl" / "common" / "helper.sv")) == 1


def test_filelist_options_reach_genus_generated_script(tmp_path: Path) -> None:
    flist = _write_filelist_project(tmp_path)
    outdir = tmp_path / "syn_out"
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "genus", 'echo GENUS_FAKE "$@"')

    result = run_script(
        RUN_SYN,
        "--tool",
        "genus",
        "--top",
        "top",
        "-f",
        str(flist),
        "--outdir",
        str(outdir),
        env=_env(fake_bin),
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    script = next((outdir / "scr").glob("genus_syn_top_*.tcl")).read_text()
    assert f"set_db init_hdl_search_path [list {tmp_path / 'rtl' / 'include'}]" in script
    assert f'read_hdl -sv -define {{FEATURE=1}} "{tmp_path / "rtl" / "leaf.sv"}"' in script
    assert script.count(str(tmp_path / "rtl" / "common" / "helper.sv")) == 1


def test_filelist_options_reach_sv2v_and_yosys_script(tmp_path: Path) -> None:
    flist = _write_filelist_project(tmp_path)
    outdir = tmp_path / "syn_out"
    fake_bin = tmp_path / "bin"
    args_file = tmp_path / "sv2v.args"
    _make_fake_tool(
        fake_bin,
        "sv2v",
        'printf "%s\\n" "$@" > "$SV2V_ARGS_FILE"; '
        'for arg in "$@"; do case "$arg" in --write=*) : > "${arg#--write=}" ;; esac; done',
    )
    _make_fake_tool(fake_bin, "yosys", 'echo YOSYS_FAKE "$@"')

    result = run_script(
        RUN_SYN,
        "--tool",
        "yosys",
        "--top",
        "top",
        "-f",
        str(flist),
        "--outdir",
        str(outdir),
        env={**_env(fake_bin), "SV2V_ARGS_FILE": str(args_file)},
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    args = args_file.read_text().splitlines()
    assert f"--write={outdir / 'temp' / 'top_sv2v.v'}" in args
    assert ["-I", str(tmp_path / "rtl" / "include")] == args[0:2]
    assert ["-D", "FEATURE=1"] == args[2:4]
    assert args.count(str(tmp_path / "rtl" / "common" / "helper.sv")) == 1
    ys = next((outdir / "scr").glob("synth_top_*.ys")).read_text()
    assert f"read_verilog {outdir / 'temp' / 'top_sv2v.v'}" in ys


def test_unsupported_filelist_token_fails(tmp_path: Path) -> None:
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "top.sv").write_text("module top; endmodule\n")
    flist = tmp_path / "rtl" / "bad.f"
    flist.write_text("-y rtl/lib\nrtl/top.sv\n")
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')

    result = run_script(
        RUN_SYN,
        "--tool",
        "dc_shell",
        "--top",
        "top",
        "-f",
        str(flist),
        "--outdir",
        str(tmp_path / "syn_out"),
        env=_env(fake_bin),
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode != 0
    assert "unsupported synthesis filelist token '-y'" in result.stderr


def test_wildcard_filelist_token_is_rejected_before_expansion(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.sv").write_text("module top; endmodule\n")
    flist = rtl / "wild.f"
    flist.write_text("rtl/*.sv\n")
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')

    result = run_script(
        RUN_SYN,
        "--tool",
        "dc_shell",
        "--top",
        "top",
        "-f",
        str(flist),
        "--outdir",
        str(tmp_path / "syn_out"),
        env=_env(fake_bin),
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode != 0
    assert "unsupported wildcard/glob token 'rtl/*.sv'" in result.stderr
    assert not list((tmp_path / "syn_out" / "scr").glob("dc_syn_top_*.tcl"))


def test_recursive_filelist_cycle_fails(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    first = rtl / "a.f"
    second = rtl / "b.f"
    first.write_text("-f rtl/b.f\n")
    second.write_text("-f rtl/a.f\n")
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')

    result = run_script(
        RUN_SYN,
        "--tool",
        "dc_shell",
        "--top",
        "top",
        "-f",
        str(first),
        "--outdir",
        str(tmp_path / "syn_out"),
        env=_env(fake_bin),
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode != 0
    assert "recursive synthesis filelist include cycle" in result.stderr
