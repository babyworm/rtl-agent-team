"""Security hardening + RAT_PROJECT_ROOT tests for EDA runner scripts.

Covers three contracts introduced by the eval-hardening pass:
1. Shell-metacharacter injection in filenames / module names / script paths is
   rejected (or neutralized via argv arrays) BEFORE any tool executes.
2. Valid inputs still work: bash -n on every hardened script plus fake-tool
   happy paths through the previously eval'd code paths.
3. RAT_PROJECT_ROOT env override: set -> relative paths resolve against the
   project root; unset -> identical to the old $(pwd) behavior.
"""

import os
import subprocess

from tests.conftest import SCRIPTS_DIR, SKILLS_DIR, run_script

TEMPLATES = SKILLS_DIR / "rat-init-project" / "templates"
RUN_SIM = SCRIPTS_DIR / "run_sim.sh"
RUN_LINT = TEMPLATES / "run_lint.sh"
RUN_CDC = TEMPLATES / "run_cdc.sh"
RUN_SYN = TEMPLATES / "run_syn.sh"
RUN_CONFORMAL = TEMPLATES / "run_conformal.sh"
RUN_FORMALITY = TEMPLATES / "run_formality.sh"
RUN_REGRESSION_UVM = (
    SKILLS_DIR / "rtl-p5s-uvm-verify" / "scripts" / "run_regression_uvm.sh"
)
MERGE_COVERAGE = SKILLS_DIR / "rtl-p5s-func-verify" / "scripts" / "merge_coverage.sh"

ALL_HARDENED_SCRIPTS = [
    RUN_SIM,
    RUN_LINT,
    RUN_CDC,
    RUN_SYN,
    RUN_CONFORMAL,
    RUN_FORMALITY,
    RUN_REGRESSION_UVM,
    MERGE_COVERAGE,
]


def _make_fake_tool(bin_dir, name, body='echo FAKE "$@"'):
    bin_dir.mkdir(exist_ok=True)
    tool = bin_dir / name
    tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n")
    tool.chmod(0o755)
    return tool


def _env_with(bin_dir=None, **extra):
    env = dict(extra)
    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
    return env


class TestBashSyntax:
    """All hardened scripts must remain valid bash."""

    def test_bash_n_all_hardened_scripts(self):
        for script in ALL_HARDENED_SCRIPTS:
            proc = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            assert proc.returncode == 0, f"{script}: {proc.stderr}"


class TestInjectionRejected:
    """Metacharacters in eval-adjacent inputs are rejected before any tool runs."""

    def test_run_lint_source_cmd_substitution_rejected(self, tmp_path):
        marker = tmp_path / "pwned"
        result = run_script(
            RUN_LINT, "--tool", "verilator", "--outdir", str(tmp_path / "out"),
            f"good$(touch {marker}).sv",
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not marker.exists()

    def test_run_lint_top_injection_rejected(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        result = run_script(
            RUN_LINT, "--tool", "verilator", "--top", "m; touch pwned",
            "--outdir", str(tmp_path / "out"), str(sv),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_cdc_script_backtick_rejected(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        result = run_script(
            RUN_CDC, "--tool", "vc_cdc", "--script", "evil`touch pwned`.tcl",
            "--outdir", str(tmp_path / "out"), str(sv),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_cdc_spyglass_filelist_entry_rejected(self, tmp_path):
        flist = tmp_path / "f.f"
        flist.write_text("rtl/x;touch pwned;.sv\n")
        result = run_script(
            RUN_CDC, "--tool", "spyglass", "-f", str(flist),
            "--outdir", str(tmp_path / "out"),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_cdc_svlens_source_injection_rejected(self, tmp_path):
        """svlens paths serialize argv into CMD echo + replay script — a source
        filename with shell metacharacters must be rejected before invocation."""
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "svlens", 'echo SVLENS_FAKE "$@"')
        sv = tmp_path / "m`touch pwned`.sv"
        sv.write_text("module m; endmodule\n")
        result = run_script(
            RUN_CDC, "--tool", "svlens", "--top", "m",
            "--outdir", str(tmp_path / "out"), str(sv),
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()
        assert "SVLENS_FAKE" not in result.stdout, "tool must not run on invalid input"

    def test_run_cdc_svlens_happy_path_with_fake_tool(self, tmp_path):
        """Valid inputs still reach svlens after replay-serialization validation."""
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "svlens", 'echo SVLENS_FAKE "$@"')
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        result = run_script(
            RUN_CDC, "--tool", "svlens", "--top", "m",
            "--outdir", str(tmp_path / "out"), str(sv),
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode == 0, result.stderr
        assert "SVLENS_FAKE" in result.stdout

    def test_run_cdc_vc_cdc_outdir_injection_rejected(self, tmp_path):
        """Every CDC branch's replay script embeds OUTDIR as cd "$RUN_CWD" —
        a $()/backtick outdir must be rejected before mkdir/replay write."""
        (tmp_path / "t.tcl").write_text("puts ok\n")
        result = run_script(
            RUN_CDC, "--tool", "vc_cdc", "--script", str(tmp_path / "t.tcl"),
            "--outdir", "out`touch pwned`",
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_cdc_questa_cdc_outdir_injection_rejected(self, tmp_path):
        (tmp_path / "t.do").write_text("puts ok\n")
        result = run_script(
            RUN_CDC, "--tool", "questa_cdc", "--script", str(tmp_path / "t.do"),
            "--outdir", "out$(touch pwned)",
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_conformal_top_non_identifier_rejected(self, tmp_path):
        (tmp_path / "m.sv").write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text("m.sv\n")
        result = run_script(
            RUN_CONFORMAL, "--top", 'm"; touch pwned; "',
            "--rtl", str(flist), "--netlist", str(tmp_path / "n.v"),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "identifier" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_conformal_netlist_injection_rejected(self, tmp_path):
        (tmp_path / "m.sv").write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text("m.sv\n")
        result = run_script(
            RUN_CONFORMAL, "--top", "m", "--rtl", str(flist),
            "--netlist", "net$(touch pwned).v",
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_formality_svf_injection_rejected(self, tmp_path):
        (tmp_path / "m.sv").write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text("m.sv\n")
        result = run_script(
            RUN_FORMALITY, "--top", "m", "--rtl", str(flist),
            "--netlist", str(tmp_path / "n.v"),
            "--svf", "guide$(touch pwned).svf",
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_syn_script_arg_tcl_unsafe_rejected(self, tmp_path):
        """--script is the eval'd dc_shell -f argument; must join the Tcl check."""
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')
        result = run_script(
            RUN_SYN, "--tool", "dc_shell", "--top", "m", "-f", str(flist),
            "--outdir", str(tmp_path / "syn_out"),
            "--script", "/tmp/evil$(touch pwned).tcl",
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=20,
        )
        assert result.returncode != 0
        assert "Tcl-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_sim_top_injection_rejected(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        result = run_script(
            RUN_SIM, "--top", "tb; touch pwned", "--compile-only", str(sv),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not (tmp_path / "pwned").exists()

    def test_run_sim_filelist_entry_injection_rejected(self, tmp_path):
        marker = tmp_path / "pwned"
        flist = tmp_path / "f.f"
        flist.write_text(f"m$(touch {marker}).sv\n")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "tb", "--compile-only",
            "--filelist", str(flist),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode != 0
        assert "shell-unsafe" in result.stderr
        assert not marker.exists()

    def test_merge_coverage_lcov_filename_not_evaled(self, tmp_path):
        """A hostile .info filename must reach lcov as a literal argv element."""
        reg = tmp_path / "sim" / "regression"
        reg.mkdir(parents=True)
        # marker is cwd-relative: the script runs with cwd=tmp_path, so an
        # eval'd $(touch pwned) would create tmp_path/pwned.
        marker = tmp_path / "pwned"
        evil_name = "a$(touch pwned).info"
        (reg / evil_name).write_text("TN:test\nend_of_record\n")
        fake_bin = tmp_path / "bin"
        log = tmp_path / "lcov_args.log"
        _make_fake_tool(fake_bin, "lcov", f'printf "%s\\n" "$@" >> "{log}"')
        _make_fake_tool(fake_bin, "genhtml", "echo genhtml ok")
        result = run_script(
            MERGE_COVERAGE,
            env=_env_with(fake_bin, FORMAT="lcov", OUTPUT=str(tmp_path / "merged.info")),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode == 0, result.stderr
        assert not marker.exists()          # eval would have executed the $(...)
        assert evil_name in log.read_text() # passed to lcov literally


class TestValidInputsStillWork:
    """Fake-tool happy paths through the previously eval'd code paths."""

    def test_run_lint_verilator_happy_path(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        outdir = tmp_path / "lint_out"
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "verilator", 'echo VERILATOR_FAKE "$@"')
        result = run_script(
            RUN_LINT, "--tool", "verilator", "--top", "m",
            "--outdir", str(outdir), str(sv),
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        replay = outdir / "replay" / "run_lint_verilator_latest.sh"
        assert replay.exists()
        text = replay.read_text()
        assert "verilator --lint-only -Wall -Wpedantic -sv --top-module m" in text
        assert str(sv) in text

    def test_run_cdc_questa_happy_path(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        tcl = tmp_path / "cdc.do"
        tcl.write_text("# do file\n")
        outdir = tmp_path / "cdc_out"
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "qverify", 'echo QVERIFY_FAKE "$@"')
        result = run_script(
            RUN_CDC, "--tool", "questa_cdc", "--script", str(tcl),
            "--outdir", str(outdir), str(sv),
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        replay = outdir / "replay" / "run_cdc_questa_cdc_latest.sh"
        assert replay.exists()
        assert "qverify -c -do" in replay.read_text()

    def test_run_conformal_happy_path(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        netlist = tmp_path / "n.v"
        netlist.write_text("module m; endmodule\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "lec", 'echo LEC_FAKE "$@"')
        result = run_script(
            RUN_CONFORMAL, "--top", "m", "--rtl", str(flist),
            "--netlist", str(netlist), "--outdir", "syn_rpt",
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        outdir = tmp_path / "syn_rpt"
        assert list(outdir.glob("conformal_m_*.log"))
        dofiles = list(outdir.glob("conformal_m_*.do"))
        assert dofiles and "read design -golden" in dofiles[0].read_text()
        replay = outdir / "replay" / "run_conformal_m_latest.sh"
        assert replay.exists()
        assert "lec -64bit -dofile" in replay.read_text()

    def test_run_formality_happy_path(self, tmp_path):
        sv = tmp_path / "m.sv"
        sv.write_text("module m; endmodule\n")
        flist = tmp_path / "f.f"
        flist.write_text(str(sv) + "\n")
        netlist = tmp_path / "n.v"
        netlist.write_text("module m; endmodule\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "fm_shell", "echo VERIFICATION PASSED")
        result = run_script(
            RUN_FORMALITY, "--top", "m", "--rtl", str(flist),
            "--netlist", str(netlist), "--outdir", "syn_rpt",
            env=_env_with(fake_bin), cwd=str(tmp_path), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        outdir = tmp_path / "syn_rpt"
        replay = outdir / "replay" / "run_formality_m_latest.sh"
        assert replay.exists()
        assert "fm_shell -64bit -f" in replay.read_text()

    def test_merge_coverage_lcov_valid_merge(self, tmp_path):
        reg = tmp_path / "sim" / "regression"
        reg.mkdir(parents=True)
        (reg / "seed_1.info").write_text("TN:t\nend_of_record\n")
        (reg / "seed_2.info").write_text("TN:t\nend_of_record\n")
        fake_bin = tmp_path / "bin"
        log = tmp_path / "lcov_args.log"
        _make_fake_tool(fake_bin, "lcov", f'printf "%s\\n" "$@" >> "{log}"')
        _make_fake_tool(fake_bin, "genhtml", "echo genhtml ok")
        result = run_script(
            MERGE_COVERAGE,
            env=_env_with(fake_bin, FORMAT="lcov", OUTPUT=str(tmp_path / "merged.info")),
            cwd=str(tmp_path), timeout=15,
        )
        assert result.returncode == 0, result.stderr
        assert "Merged 2 coverage files" in result.stdout
        args = log.read_text()
        assert str(reg / "seed_1.info") not in args  # find yields relative paths
        assert "--add-tracefile" in args
        assert "sim/regression/seed_1.info" in args
        assert "sim/regression/seed_2.info" in args


class TestRatProjectRootOverride:
    """RAT_PROJECT_ROOT set -> root honored; unset -> $(pwd) (old behavior)."""

    IVERILOG_FAKE = (
        "out=''; while [ $# -gt 0 ]; do "
        "if [ \"$1\" = '-o' ]; then out=\"$2\"; shift 2; continue; fi; shift; done; "
        '[ -n "$out" ] && : > "$out"'
    )

    def test_run_sim_honors_rat_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (proj / "m.sv").write_text("module m; endmodule\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "iverilog", self.IVERILOG_FAKE)
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "m", "--compile-only",
            "--outdir", "simout", "m.sv",
            env=_env_with(fake_bin, RAT_PROJECT_ROOT=str(proj)),
            cwd=str(other), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert (proj / "simout").exists()
        assert not (other / "simout").exists()

    def test_run_sim_unset_uses_pwd(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (other / "m.sv").write_text("module m; endmodule\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "iverilog", self.IVERILOG_FAKE)
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "m", "--compile-only",
            "--outdir", "simout", "m.sv",
            env=_env_with(fake_bin),
            cwd=str(other), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert (other / "simout").exists()
        assert not (proj / "simout").exists()

    def test_run_lint_honors_rat_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (proj / "m.sv").write_text("module m; endmodule\n")
        (proj / "f.f").write_text("m.sv\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "verilator", 'echo VERILATOR_FAKE "$@"')
        result = run_script(
            RUN_LINT, "--tool", "verilator", "--top", "m",
            "-f", "f.f", "--outdir", "lint_out",
            env=_env_with(fake_bin, RAT_PROJECT_ROOT=str(proj)),
            cwd=str(other), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        replay = proj / "lint_out" / "replay" / "run_lint_verilator_latest.sh"
        assert replay.exists()
        assert str(proj / "m.sv") in replay.read_text()
        assert not (other / "lint_out").exists()

    def test_run_syn_honors_rat_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (proj / "m.sv").write_text("module m; endmodule\n")
        (proj / "f.f").write_text("m.sv\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "dc_shell", 'echo DC_FAKE "$@"')
        result = run_script(
            RUN_SYN, "--tool", "dc_shell", "--top", "m",
            "-f", "f.f", "--outdir", "syn_out",
            env=_env_with(fake_bin, RAT_PROJECT_ROOT=str(proj)),
            cwd=str(other), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert (proj / "syn_out" / "scr").exists()
        assert list((proj / "syn_out" / "scr").glob("dc_syn_m_*.tcl"))
        assert not (other / "syn_out").exists()

    def test_run_cdc_structural_honors_rat_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (proj / "m.sv").write_text(
            "module m(input logic sys_clk, input logic axi_clk); endmodule\n"
        )
        (proj / "f.f").write_text("m.sv\n")
        result = run_script(
            RUN_CDC, "--tool", "structural", "-f", "f.f", "--outdir", "cdc_out",
            env=_env_with(None, RAT_PROJECT_ROOT=str(proj)),
            cwd=str(other), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert list((proj / "cdc_out").glob("cdc_structural_*.log"))
        assert not (other / "cdc_out").exists()

    def test_run_conformal_honors_rat_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (proj / "m.sv").write_text("module m; endmodule\n")
        (proj / "f.f").write_text("m.sv\n")
        (proj / "n.v").write_text("module m; endmodule\n")
        fake_bin = tmp_path / "bin"
        _make_fake_tool(fake_bin, "lec", 'echo LEC_FAKE "$@"')
        result = run_script(
            RUN_CONFORMAL, "--top", "m", "--rtl", "f.f", "--netlist", "n.v",
            env=_env_with(fake_bin, RAT_PROJECT_ROOT=str(proj)),
            cwd=str(other), timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert list((proj / "syn" / "rpt").glob("conformal_m_*.log"))
        assert not (other / "syn").exists()

    def test_run_regression_uvm_honors_rat_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        rtl = proj / "rtl"
        rtl.mkdir()
        (rtl / "m.sv").write_text("module m; endmodule\n")
        (rtl / "filelist_top.f").write_text("rtl/m.sv\n")
        fake_bin = tmp_path / "bin"
        # Fake vcs: create an executable simv at the -o target so run_seed works.
        _make_fake_tool(
            fake_bin, "vcs",
            "out=''; while [ $# -gt 0 ]; do "
            "if [ \"$1\" = '-o' ]; then out=\"$2\"; shift 2; continue; fi; shift; done; "
            'if [ -n "$out" ]; then printf \'#!/usr/bin/env bash\\necho SIMV_FAKE\\n\' > "$out"; '
            'chmod +x "$out"; fi',
        )
        result = run_script(
            RUN_REGRESSION_UVM, "--sim", "vcs", "--seeds", "42",
            "--parallel", "1", "--module", "topx",
            env=_env_with(fake_bin, RAT_PROJECT_ROOT=str(proj)),
            cwd=str(other), timeout=30,
        )
        assert result.returncode == 0, result.stderr
        results_dir = proj / "sim" / "uvm" / "regression"
        assert results_dir.exists()
        reports = list(results_dir.glob("regression_topx_*.json"))
        assert reports
        assert '"verdict": "PASS"' in reports[0].read_text()
        assert not (other / "sim").exists()
