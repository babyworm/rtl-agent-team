"""Equivalence-wrapper and Makefile safety contracts."""

import os
import subprocess
from pathlib import Path

from tests.conftest import REPO_ROOT, run_script

TEMPLATES = REPO_ROOT / "skills" / "rat-init-project" / "templates"
RUN_CONFORMAL = TEMPLATES / "run_conformal.sh"
RUN_FORMALITY = TEMPLATES / "run_formality.sh"
MAKEFILE = TEMPLATES / "Makefile"
EQUIV_AGENT = REPO_ROOT / "agents" / "equivalence-checker.md"


def _make_fake_tool(bin_dir: Path, name: str, body: str) -> Path:
    bin_dir.mkdir(exist_ok=True)
    tool = bin_dir / name
    tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n")
    tool.chmod(0o755)
    return tool


def _env_with(bin_dir: Path) -> dict[str, str]:
    return {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}


def _basic_design(tmp_path: Path) -> tuple[Path, Path]:
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "include").mkdir()
    (rtl / "m.sv").write_text("module m; endmodule\n")
    (rtl / "child.sv").write_text("module child; endmodule\n")
    nested = tmp_path / "nested.f"
    nested.write_text("+define+WIDTH=8\nrtl/child.sv\n")
    flist = tmp_path / "top.f"
    flist.write_text("+incdir+rtl/include\n-f nested.f\nrtl/m.sv\n")
    netlist = tmp_path / "n.v"
    netlist.write_text("module m; endmodule\n")
    return flist, netlist


def test_conformal_fails_closed_on_non_equivalent_exit_zero(tmp_path: Path) -> None:
    flist, netlist = _basic_design(tmp_path)
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "lec", "echo NON-EQUIVALENT; exit 0")

    result = run_script(
        RUN_CONFORMAL,
        "--top",
        "m",
        "--rtl",
        str(flist),
        "--netlist",
        str(netlist),
        "--outdir",
        "rpt",
        cwd=tmp_path,
        env=_env_with(fake_bin),
        timeout=20,
    )

    assert result.returncode != 0
    assert "failing/aborted/unknown" in result.stderr


def test_conformal_requires_explicit_success_marker(tmp_path: Path) -> None:
    flist, netlist = _basic_design(tmp_path)
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "lec", "echo LEC_FINISHED_BUT_NO_STATUS; exit 0")

    result = run_script(
        RUN_CONFORMAL,
        "--top",
        "m",
        "--rtl",
        str(flist),
        "--netlist",
        str(netlist),
        "--outdir",
        "rpt",
        cwd=tmp_path,
        env=_env_with(fake_bin),
        timeout=20,
    )

    assert result.returncode != 0
    assert "accepted equivalence success marker" in result.stderr


def test_conformal_happy_path_preserves_recursive_filelist_options(tmp_path: Path) -> None:
    flist, netlist = _basic_design(tmp_path)
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "lec", "echo RAT_CONFORMAL_EQUIVALENT")

    result = run_script(
        RUN_CONFORMAL,
        "--top",
        "m",
        "--rtl",
        str(flist),
        "--netlist",
        str(netlist),
        "--outdir",
        "rpt",
        cwd=tmp_path,
        env=_env_with(fake_bin),
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    dofile = next((tmp_path / "rpt").glob("conformal_m_*.do"))
    text = dofile.read_text()
    assert "read design -golden -sv" in text
    assert f'"+incdir+{tmp_path / "rtl" / "include"}"' in text
    assert '"+define+WIDTH=8"' in text
    assert f'"{tmp_path / "rtl" / "child.sv"}"' in text
    assert "read design -revised -verilog2k" in text


def test_conformal_accepts_common_pass_marker_with_zero_error_count(tmp_path: Path) -> None:
    flist, netlist = _basic_design(tmp_path)
    fake_bin = tmp_path / "bin"
    _make_fake_tool(
        fake_bin,
        "lec",
        "echo 'ERROR count: 0'; echo 'Compare Results: PASS'",
    )

    result = run_script(
        RUN_CONFORMAL,
        "--top",
        "m",
        "--rtl",
        str(flist),
        "--netlist",
        str(netlist),
        "--outdir",
        "rpt",
        cwd=tmp_path,
        env=_env_with(fake_bin),
        timeout=20,
    )

    assert result.returncode == 0, result.stderr


def test_conformal_accepts_equivalent_compare_results_marker(tmp_path: Path) -> None:
    flist, netlist = _basic_design(tmp_path)
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "lec", "echo 'Compare Results: EQUIVALENT'")

    result = run_script(
        RUN_CONFORMAL,
        "--top",
        "m",
        "--rtl",
        str(flist),
        "--netlist",
        str(netlist),
        "--outdir",
        "rpt",
        cwd=tmp_path,
        env=_env_with(fake_bin),
        timeout=20,
    )

    assert result.returncode == 0, result.stderr


def test_formality_uses_systemverilog_and_preserves_filelist_options(tmp_path: Path) -> None:
    flist, netlist = _basic_design(tmp_path)
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "fm_shell", "echo VERIFICATION PASSED")

    result = run_script(
        RUN_FORMALITY,
        "--top",
        "m",
        "--rtl",
        str(flist),
        "--netlist",
        str(netlist),
        "--outdir",
        "rpt",
        cwd=tmp_path,
        env=_env_with(fake_bin),
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    tcl = next((tmp_path / "rpt").glob("formality_m_*.tcl"))
    text = tcl.read_text()
    assert "read_sverilog -container r -libname WORK" in text
    assert "read_verilog -container r -libname WORK -05" not in text
    assert f'"+incdir+{tmp_path / "rtl" / "include"}"' in text
    assert '"+define+WIDTH=8"' in text
    assert f'"{tmp_path / "rtl" / "child.sv"}"' in text
    assert "read_verilog -container i -libname WORK -05" in text


def test_makefile_quotes_synthesis_and_formal_recipe_variables() -> None:
    text = MAKEFILE.read_text()
    for needle in [
        "$(call _validate_path_var,FILELIST)",
        "$(call _validate_path_var,SYN_SCRIPT)",
        '"$(SYN_SCRIPT)" --tool yosys --top "$(TOP)" -f "$(FILELIST)"',
        '"$(SYN_SCRIPT)" --tool dc_shell --top "$(TOP)" -f "$(FILELIST)"',
        '"$(SYN_SCRIPT)" --tool genus --top "$(TOP)" -f "$(FILELIST)"',
        "$(call _validate_path_var,SBY_FILE)",
        'sby -f "$(SBY_FILE)" bmc prove cover',
        'jg -batch "$(abspath $(JASPER_TCL))"',
        'vcf -f "$(abspath $(VCF_TCL))" -batch',
    ]:
        assert needle in text
    assert "cd formal && sby" not in text


def test_makefile_rejects_top_command_substitution_before_recipe(tmp_path: Path) -> None:
    marker = tmp_path / "pwned_top"
    result = subprocess.run(
        [
            "make",
            "-f",
            str(MAKEFILE),
            "syn_yosys",
            f"TOP=$$(touch {marker})",
            "FILELIST=rtl/filelist_top.f",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "TOP must not contain whitespace" in result.stderr
    assert not marker.exists()


def test_makefile_rejects_filelist_command_substitution_before_recipe(tmp_path: Path) -> None:
    marker = tmp_path / "pwned_filelist"
    result = subprocess.run(
        [
            "make",
            "-f",
            str(MAKEFILE),
            "syn_yosys",
            "TOP=m",
            f"FILELIST=rtl/filelist$$(touch {marker}).f",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "FILELIST must not contain whitespace" in result.stderr
    assert not marker.exists()


def test_makefile_rejects_syn_script_command_substitution_before_recipe(tmp_path: Path) -> None:
    marker = tmp_path / "pwned_script"
    result = subprocess.run(
        [
            "make",
            "-f",
            str(MAKEFILE),
            "syn_yosys",
            "TOP=m",
            "FILELIST=rtl/filelist_top.f",
            f"SYN_SCRIPT=$$(touch {marker})",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "SYN_SCRIPT must not contain whitespace" in result.stderr
    assert not marker.exists()


def test_nested_equivalence_filelist_entries_resolve_from_including_file(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    nested_dir = rtl / "sub"
    nested_dir.mkdir(parents=True)
    include_dir = nested_dir / "include"
    include_dir.mkdir()
    child = nested_dir / "child.sv"
    child.write_text("module child; endmodule\n")
    (rtl / "top.sv").write_text("module m; endmodule\n")
    (nested_dir / "nested.f").write_text(
        "# nested comment\n+incdir+include\nchild.sv\n"
    )
    flist = tmp_path / "top.f"
    flist.write_text("-f rtl/sub/nested.f\nrtl/top.sv\n")
    netlist = tmp_path / "n.v"
    netlist.write_text("module m; endmodule\n")
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "lec", "echo 'Compare Results: PASS'")
    _make_fake_tool(fake_bin, "fm_shell", "echo VERIFICATION PASSED")

    conformal = run_script(
        RUN_CONFORMAL,
        "--top", "m", "--rtl", str(flist), "--netlist", str(netlist), "--outdir", "rpt",
        cwd=tmp_path, env=_env_with(fake_bin), timeout=20,
    )
    formality = run_script(
        RUN_FORMALITY,
        "--top", "m", "--rtl", str(flist), "--netlist", str(netlist), "--outdir", "rpt_fm",
        cwd=tmp_path, env=_env_with(fake_bin), timeout=20,
    )

    assert conformal.returncode == 0, conformal.stderr
    assert formality.returncode == 0, formality.stderr
    dofile = next((tmp_path / "rpt").glob("conformal_m_*.do")).read_text()
    tcl = next((tmp_path / "rpt_fm").glob("formality_m_*.tcl")).read_text()
    for text in (dofile, tcl):
        assert str(child) in text
        assert f"+incdir+{include_dir}" in text


def test_equivalence_agent_does_not_reintroduce_eval_or_bad_sv2v_option() -> None:
    text = EQUIV_AGENT.read_text()
    assert "eval $(" not in text
    assert "read_sverilog -container r -libname WORK" in text
    assert "--write=/tmp/reference.v" in text
    assert " -o /tmp/reference.v" not in text


def test_project_root_filelist_entries_do_not_gain_a_second_rtl_prefix(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    nested_dir = rtl / "sub"
    nested_dir.mkdir(parents=True)
    child = nested_dir / "child.sv"
    child.write_text("module child; endmodule\n")
    (rtl / "top.sv").write_text("module m; endmodule\n")
    (nested_dir / "nested.f").write_text("rtl/sub/child.sv\n")
    flist = rtl / "filelist_top.f"
    flist.write_text("-f rtl/sub/nested.f\nrtl/top.sv\n")
    netlist = tmp_path / "n.v"
    netlist.write_text("module m; endmodule\n")
    fake_bin = tmp_path / "bin"
    _make_fake_tool(fake_bin, "lec", "echo 'Compare Results: PASS'")
    _make_fake_tool(fake_bin, "fm_shell", "echo VERIFICATION PASSED")

    conformal = run_script(
        RUN_CONFORMAL,
        "--top", "m", "--rtl", "rtl/filelist_top.f", "--netlist", "n.v", "--outdir", "rpt",
        cwd=tmp_path, env=_env_with(fake_bin), timeout=20,
    )
    formality = run_script(
        RUN_FORMALITY,
        "--top", "m", "--rtl", "rtl/filelist_top.f", "--netlist", "n.v", "--outdir", "rpt_fm",
        cwd=tmp_path, env=_env_with(fake_bin), timeout=20,
    )

    assert conformal.returncode == 0, conformal.stderr
    assert formality.returncode == 0, formality.stderr
    dofile = next((tmp_path / "rpt").glob("conformal_m_*.do")).read_text()
    tcl = next((tmp_path / "rpt_fm").glob("formality_m_*.tcl")).read_text()
    for text in (dofile, tcl):
        assert str(child) in text
        assert str(rtl / "top.sv") in text
        assert "rtl/rtl/" not in text
