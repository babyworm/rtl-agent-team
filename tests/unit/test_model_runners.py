"""CLI tests for the model build-and-run wrappers.

Covers `skills/ref-model/scripts/run_ref_model.py` (Phase 2 C reference
model) and `skills/bfm-develop/scripts/run_bfm.py` (Phase 3 SystemC BFM).

All invocations go through subprocess so the argparse CLI surface is
exercised exactly as the skills document it. SystemC is NOT required:
run_bfm.py orchestration is validated against fake build trees whose
Makefile targets are plain sh (the committed
`examples/selfcheck_fake_build/` fixture and tmp-dir variants). The
ref-model example compiles a tiny self-testing C model with the system C
compiler and is skipped gracefully when no compiler is present.

Exit code contract shared by both scripts:
  0 = build + run OK, 1 = build/run failure (report still written),
  2 = usage/environment error.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"

REF_MODEL_DIR = SKILLS_DIR / "ref-model"
BFM_DEV_DIR = SKILLS_DIR / "bfm-develop"
RUN_REF_MODEL = REF_MODEL_DIR / "scripts" / "run_ref_model.py"
RUN_BFM = BFM_DEV_DIR / "scripts" / "run_bfm.py"
SAT_ADD_EXAMPLE = REF_MODEL_DIR / "examples" / "sat_add"
FAKE_BUILD_EXAMPLE = BFM_DEV_DIR / "examples" / "selfcheck_fake_build"

HAS_CC = any(shutil.which(c) for c in ("cc", "gcc", "clang"))
HAS_MAKE = shutil.which("make") is not None

requires_cc = pytest.mark.skipif(not HAS_CC, reason="no system C compiler")
requires_make = pytest.mark.skipif(not HAS_MAKE, reason="no make on PATH")
requires_cc_and_make = pytest.mark.skipif(
    not (HAS_CC and HAS_MAKE), reason="no system C compiler and/or make")

# Fields documented as non-deterministic — excluded from sync comparisons.
REF_NONDET_FIELDS = ("duration_seconds",)
BFM_NONDET_FIELDS = ("duration_seconds", "systemc_home_set")


def run_script(script, *args, cwd=None, env=None):
    """Run a skill script via subprocess; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=cwd, env=env, check=False)


def empty_path_env():
    """Environment whose PATH resolves no tools (compiler/make/cmake)."""
    env = dict(os.environ)
    env["PATH"] = ""
    env.pop("CC", None)
    return env


# ---------------------------------------------------------------------------
# run_ref_model.py
# ---------------------------------------------------------------------------

class TestRunRefModel:
    def test_missing_refc_dir_is_error(self, tmp_path):
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc", cwd=tmp_path)
        assert result.returncode == 2
        assert "refc directory not found" in result.stderr

    def test_no_compiler_and_no_makefile_is_error(self, tmp_path):
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "model.c").write_text("int main(void){return 0;}\n")
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            cwd=tmp_path, env=empty_path_env())
        assert result.returncode == 2
        assert "no C compiler found" in result.stderr

    def test_makefile_without_make_is_error(self, tmp_path):
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "Makefile").write_text("all:\n\ttrue\n")
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            cwd=tmp_path, env=empty_path_env())
        assert result.returncode == 2
        assert "'make' is not on PATH" in result.stderr

    @requires_cc_and_make
    def test_sat_add_example_end_to_end(self, tmp_path):
        work = tmp_path / "sat_add"
        shutil.copytree(SAT_ADD_EXAMPLE, work)
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            "--report", "run_report.json", cwd=work)
        assert result.returncode == 0, result.stderr
        report = json.loads((work / "run_report.json").read_text())
        assert report["built"] is True
        assert report["build_mode"] == "make"
        assert report["exit_code"] == 0
        assert "SELF-TEST PASS" in report["stdout_tail"]
        assert report["run_cmd"] == ["refc/build/sat_add_ref"]

    @requires_cc_and_make
    def test_committed_expected_report_matches_regeneration(self, tmp_path):
        """examples/sat_add/expected_run_report.json must stay in sync with
        the runner (deterministic fields only)."""
        work = tmp_path / "sat_add"
        shutil.copytree(SAT_ADD_EXAMPLE, work)
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            "--report", "run_report.json", cwd=work)
        assert result.returncode == 0, result.stderr
        regenerated = json.loads((work / "run_report.json").read_text())
        committed = json.loads(
            (SAT_ADD_EXAMPLE / "expected_run_report.json").read_text())
        for field in REF_NONDET_FIELDS:
            regenerated.pop(field)
            committed.pop(field)
        assert regenerated == committed

    @requires_cc
    def test_direct_cc_fallback_without_makefile(self, tmp_path):
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "model.c").write_text(
            '#include <stdio.h>\n'
            'int main(void){printf("model ok\\n");return 0;}\n')
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["build_mode"] == "cc"
        assert report["build_cmds"][0][-1] == "model.c"
        assert "-std=c11" in report["build_cmds"][0]
        assert report["run_cmd"] == ["refc/build/ref_model"]
        assert report["stdout_tail"] == ["model ok"]

    @requires_cc
    def test_model_nonzero_exit_is_exit1_with_report(self, tmp_path):
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "model.c").write_text("int main(void){return 3;}\n")
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 1
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["built"] is True
        assert report["exit_code"] == 3

    @requires_make
    def test_build_failure_is_exit1_with_report(self, tmp_path):
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "Makefile").write_text("all:\n\t@exit 7\n")
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 1
        assert "build failed" in result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["built"] is False
        # build_exit_code records the build *tool*'s exit code (make wraps
        # the recipe's status — GNU make reports 2), so assert non-zero.
        assert report["build_exit_code"] != 0
        assert report["exit_code"] is None

    @requires_make
    def test_input_output_args_passthrough_and_output_recorded(self, tmp_path):
        """--input/--output/--args are forwarded verbatim; the --output file
        is recorded with its byte size. Uses a sh 'binary' so no compiler
        is needed."""
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "Makefile").write_text(
            "all:\n"
            "\t@mkdir -p build\n"
            "\t@printf '#!/bin/sh\\ncp \"$$2\" \"$$4\"\\necho \"mode=$$5\"\\n'"
            " > build/copy_model\n"
            "\t@chmod +x build/copy_model\n")
        (tmp_path / "in.bin").write_bytes(b"\x01\x02\x03")
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc",
                            "--input", "in.bin", "--output", "out.bin",
                            "--args", "--lanes 4",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["run_cmd"] == ["refc/build/copy_model",
                                     "--input", "in.bin",
                                     "--output", "out.bin",
                                     "--lanes", "4"]
        assert report["output_files"] == [{"path": "out.bin", "bytes": 3}]
        assert (tmp_path / "out.bin").read_bytes() == b"\x01\x02\x03"

    @requires_make
    def test_no_binary_after_build_is_error(self, tmp_path):
        refc = tmp_path / "refc"
        refc.mkdir()
        (refc / "Makefile").write_text("all:\n\t@true\n")
        result = run_script(RUN_REF_MODEL, "--refc-dir", "refc", cwd=tmp_path)
        assert result.returncode == 2
        assert "no runnable binary" in result.stderr


# ---------------------------------------------------------------------------
# run_bfm.py
# ---------------------------------------------------------------------------

def write_fake_bfm_makefile(bfm_dir, with_run=True, systemc_ref=False,
                            fail_build=False):
    """Fake build tree: all/run targets are plain sh — no SystemC needed."""
    lines = []
    if systemc_ref:
        lines += ["SYSTEMC_INC = -I$(SYSTEMC_HOME)/include", ""]
    if fail_build:
        lines += ["all:", "\t@exit 9", ""]
    else:
        lines += [
            "all:",
            "\t@mkdir -p build",
            "\t@printf '#!/bin/sh\\necho \"BFM smoke: PASS\"\\n'"
            " > build/fake_bfm",
            "\t@chmod +x build/fake_bfm",
            "",
        ]
    if with_run:
        lines += [
            "run: all",
            "\t@./build/fake_bfm > smoke_test_result.txt",
            "\t@cat smoke_test_result.txt",
            "",
        ]
    lines += [".PHONY: all run clean", ""]
    (bfm_dir / "Makefile").write_text("\n".join(lines))


class TestRunBfm:
    def test_missing_bfm_dir_is_error(self, tmp_path):
        result = run_script(RUN_BFM, "--bfm-dir", "bfm", cwd=tmp_path)
        assert result.returncode == 2
        assert "bfm directory not found" in result.stderr

    def test_no_build_system_is_error(self, tmp_path):
        (tmp_path / "bfm").mkdir()
        result = run_script(RUN_BFM, "--bfm-dir", "bfm", cwd=tmp_path)
        assert result.returncode == 2
        assert "no CMakeLists.txt or Makefile" in result.stderr

    def test_systemc_home_referenced_but_unset_is_error(self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        write_fake_bfm_makefile(bfm, systemc_ref=True)
        env = dict(os.environ)
        env.pop("SYSTEMC_HOME", None)
        result = run_script(RUN_BFM, "--bfm-dir", "bfm", cwd=tmp_path, env=env)
        assert result.returncode == 2
        assert "SYSTEMC_HOME" in result.stderr
        assert "export SYSTEMC_HOME" in result.stderr

    def test_systemc_home_mention_in_comment_only_is_not_a_reference(
            self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        write_fake_bfm_makefile(bfm)
        text = (bfm / "Makefile").read_text()
        (bfm / "Makefile").write_text(
            "# does not use SYSTEMC_HOME at build time\n" + text)
        env = dict(os.environ)
        env.pop("SYSTEMC_HOME", None)
        if not HAS_MAKE:
            pytest.skip("no make on PATH")
        result = run_script(RUN_BFM, "--bfm-dir", "bfm",
                            "--report", "report.json", cwd=tmp_path, env=env)
        assert result.returncode == 0, result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["systemc_home_referenced"] is False

    @requires_make
    def test_systemc_home_set_allows_build(self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        write_fake_bfm_makefile(bfm, systemc_ref=True)
        env = dict(os.environ)
        env["SYSTEMC_HOME"] = str(tmp_path)
        result = run_script(RUN_BFM, "--bfm-dir", "bfm",
                            "--report", "report.json", cwd=tmp_path, env=env)
        assert result.returncode == 0, result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["systemc_home_referenced"] is True
        assert report["systemc_home_set"] is True

    @requires_make
    def test_fake_build_uses_make_run_target(self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        write_fake_bfm_makefile(bfm)
        result = run_script(RUN_BFM, "--bfm-dir", "bfm",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["build_system"] == "make"
        assert report["run_mode"] == "make-run"
        assert report["run_cmd"] == ["make", "run"]
        assert "BFM smoke: PASS" in report["stdout_tail"]
        assert {"path": "smoke_test_result.txt", "bytes": 16} \
            in report["output_files"]

    @requires_make
    def test_binary_mode_when_no_run_target(self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        write_fake_bfm_makefile(bfm, with_run=False)
        result = run_script(RUN_BFM, "--bfm-dir", "bfm",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["run_mode"] == "binary"
        assert report["run_cmd"] == ["bfm/build/fake_bfm"]
        assert report["stdout_tail"] == ["BFM smoke: PASS"]

    @requires_make
    def test_build_failure_is_exit1_with_report(self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        write_fake_bfm_makefile(bfm, fail_build=True)
        result = run_script(RUN_BFM, "--bfm-dir", "bfm",
                            "--report", "report.json", cwd=tmp_path)
        assert result.returncode == 1
        assert "build failed" in result.stderr
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["built"] is False
        assert report["build_exit_code"] != 0
        assert report["exit_code"] is None

    def test_cmakelists_without_cmake_is_error(self, tmp_path):
        bfm = tmp_path / "bfm"
        bfm.mkdir()
        (bfm / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.10)\nproject(fake NONE)\n")
        result = run_script(RUN_BFM, "--bfm-dir", "bfm",
                            cwd=tmp_path, env=empty_path_env())
        assert result.returncode == 2
        assert "cmake" in result.stderr

    @requires_make
    def test_committed_expected_report_matches_regeneration(self, tmp_path):
        """examples/selfcheck_fake_build/expected_run_report.json must stay
        in sync with the runner (deterministic fields only)."""
        work = tmp_path / "selfcheck_fake_build"
        shutil.copytree(FAKE_BUILD_EXAMPLE, work)
        result = run_script(RUN_BFM, "--bfm-dir", ".",
                            "--report", "run_report.json", cwd=work)
        assert result.returncode == 0, result.stderr
        regenerated = json.loads((work / "run_report.json").read_text())
        committed = json.loads(
            (FAKE_BUILD_EXAMPLE / "expected_run_report.json").read_text())
        for field in BFM_NONDET_FIELDS:
            regenerated.pop(field)
            committed.pop(field)
        assert regenerated == committed


# ---------------------------------------------------------------------------
# structural checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("script", [RUN_REF_MODEL, RUN_BFM],
                         ids=lambda p: p.name)
def test_script_compiles_and_has_help(script):
    proc = subprocess.run([sys.executable, "-m", "py_compile", str(script)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    result = run_script(script, "--help")
    assert result.returncode == 0
    assert "--report" in result.stdout


@pytest.mark.parametrize("skill_name,asset", [
    ("ref-model", "scripts/run_ref_model.py"),
    ("bfm-develop", "scripts/run_bfm.py"),
])
def test_no_deep_fill_placeholders_remain(skill_name, asset):
    """Implemented runners must not advertise stubs in code or SKILL.md."""
    script = SKILLS_DIR / skill_name / asset
    assert "NotImplementedError" not in script.read_text(), (
        f"{skill_name}/{asset} is still a stub")
    skill_md = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
    assert "deep-fill" not in skill_md, (
        f"{skill_name}/SKILL.md still carries deep-fill placeholder rows")
    row = [ln for ln in skill_md.splitlines() if f"`{asset}`" in ln]
    assert row, f"{skill_name}/SKILL.md Assets table missing {asset} row"


def test_conformance_examples_readme_replaces_gitkeep():
    examples = SKILLS_DIR / "rtl-conformance-test" / "examples"
    assert not (examples / ".gitkeep").exists(), "stale .gitkeep placeholder"
    readme = (examples / "README.md").read_text()
    assert "intentionally" in readme.lower()
    assert "JVT" in readme and "MD5" in readme
