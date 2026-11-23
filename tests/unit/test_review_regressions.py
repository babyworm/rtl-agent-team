"""Regression tests for repository review fixes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import HOOKS_DIR, REPO_ROOT, SKILLS_DIR, run_hook, run_script


def test_compliance_gate_util_no_0null_on_null_or_zero_fields(tmp_path: Path) -> None:
    state_dir = tmp_path / ".rat" / "state"
    state_dir.mkdir(parents=True)
    skill_state = state_dir / "skill-active.json"
    skill_state.write_text(json.dumps({
        "skill": "p2-arch-design",
        "pending": "compliance-pass|arch-doc#1&a",
        "strategy": "upstream_challenge",
        "compliance_authority": None,
        "max_primary": None,
        "max_fallback": None,
        "dynamic_prompt": "old",
    }))
    (state_dir / "compliance-report.json").write_text(json.dumps({
        "summary": {"verdict": "PASS"},
    }))
    sh_cmd = (
        f'. "{HOOKS_DIR / "lib" / "json-util.sh"}"\n'
        f'. "{HOOKS_DIR / "lib" / "flock-util.sh"}"\n'
        f'. "{HOOKS_DIR / "lib" / "compliance-gate-util.sh"}"\n'
        "jsonu_detect_parser\n"
        f'compliance_preprocess "{skill_state}" "{state_dir}" "compliance-pass|arch-doc#1&a"\n'
    )
    res = subprocess.run(["sh", "-c", sh_cmd], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    data = json.loads(skill_state.read_text())
    assert data["compliance_authority"] == 0
    assert data["max_primary"] == 0
    assert data["max_fallback"] == 0
    assert data["strategy"] == "primary"
    assert data["pending"] == "arch-doc#1&a"


def test_rtl_eda_context_quotes_special_chars_in_env_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "dir with space $(uname) 'q'"
    data_dir.mkdir()
    (data_dir / "env-config.json").write_text('{"schema_version": 1}\n')
    env_file = tmp_path / "claude_env.sh"
    env_file.write_text("")
    hook = HOOKS_DIR / "rtl-eda-context.sh"
    res = run_hook(
        hook,
        {"cwd": str(tmp_path), "hook_event_name": "SessionStart"},
        env={"CLAUDE_PLUGIN_DATA": str(data_dir), "CLAUDE_ENV_FILE": str(env_file)},
    )
    assert "hookSpecificOutput" in res
    check = subprocess.run(
        ["sh", "-c", f'. "{env_file}" && printf "%s" "$RAT_DATA_DIR"'],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr
    assert check.stdout == str(data_dir)


def test_verify_stop_gate_renotifies_in_notify_mode(tmp_path: Path) -> None:
    state = tmp_path / ".rat" / "state"
    state.mkdir(parents=True)
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "a.sv").write_text("module a; endmodule\n")
    (tmp_path / "rtl" / "b.sv").write_text("module b; endmodule\n")
    (tmp_path / "rat_config.json").write_text(json.dumps({"verification": {"stop_gate": "notify"}}))
    (state / "rtl-modified-files.txt").write_text("rtl/a.sv\n")

    hook = HOOKS_DIR / "rtl-verify-stop-gate.sh"
    first = run_hook(hook, {"cwd": str(tmp_path), "prompt_id": "p1", "stop_hook_active": False})
    assert "systemMessage" in first

    # Same file in continuation chain stays silent
    second = run_hook(hook, {"cwd": str(tmp_path), "prompt_id": "p1", "stop_hook_active": True})
    assert second == {"continue": True}

    # New RTL edit in same continuation chain re-notifies
    (state / "rtl-modified-files.txt").write_text("rtl/a.sv\nrtl/b.sv\n")
    third = run_hook(hook, {"cwd": str(tmp_path), "prompt_id": "p1", "stop_hook_active": True})
    assert "systemMessage" in third


def test_stray_symlink_in_state_does_not_disable_stop_gate(tmp_path: Path) -> None:
    state = tmp_path / ".rat" / "state"
    state.mkdir(parents=True)
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "a.sv").write_text("module a; endmodule\n")
    (state / "rtl-modified-files.txt").write_text("rtl/a.sv\n")
    target = tmp_path / "stray_target.txt"
    target.write_text("hi")
    (state / "stray-link").symlink_to(target)

    hook = HOOKS_DIR / "rtl-verify-stop-gate.sh"
    res = run_hook(hook, {"cwd": str(tmp_path)})
    assert res.get("decision") == "block"


def test_validate_patch_scope_blocks_rename_traversal_and_unparseable(tmp_path: Path) -> None:
    script = SKILLS_DIR / "rtl-ppa-optimize-dc" / "scripts" / "validate_patch_scope.py"

    # Rename from allowed to frozen must fail
    rename_diff = tmp_path / "rename.diff"
    rename_diff.write_text(
        "diff --git a/rtl/core/a.sv b/rtl/common/a.sv\n"
        "rename from rtl/core/a.sv\n"
        "rename to rtl/common/a.sv\n"
    )
    r1 = subprocess.run(
        [sys.executable, str(script), str(rename_diff), "rtl/core/**/*.sv", "rtl/common/**"],
        capture_output=True, text=True,
    )
    assert r1.returncode == 1

    # Traversal path must fail
    trav_diff = tmp_path / "trav.diff"
    trav_diff.write_text(
        "diff --git a/rtl/core/../../etc/passwd b/rtl/core/../../etc/passwd\n"
        "--- a/rtl/core/../../etc/passwd\n+++ b/rtl/core/../../etc/passwd\n"
    )
    r2 = subprocess.run(
        [sys.executable, str(script), str(trav_diff), "rtl/core/**/*.sv", ""],
        capture_output=True, text=True,
    )
    assert r2.returncode == 1

    # Non-empty unparseable diff must fail closed
    junk_diff = tmp_path / "junk.diff"
    junk_diff.write_text("not a valid diff header\n+injected\n")
    r3 = subprocess.run(
        [sys.executable, str(script), str(junk_diff), "rtl/core/**/*.sv", ""],
        capture_output=True, text=True,
    )
    assert r3.returncode == 1


def test_parse_yosys_stat_liberty_mapped_cells_and_latches() -> None:
    sys.path.insert(0, str(SKILLS_DIR / "rtl-synth-check" / "scripts"))
    import parse_yosys_stat as pys

    modern = (
        "=== top ===\n"
        "       10 wires\n"
        "        5 cells\n"
        "        3   NAND2_X1\n"
        "        1   DFF_X1\n"
        "        1   DLH_X1\n"
        "   Chip area for module '\\top': 12.34\n"
    )
    res = pys.parse_stat_output(modern)
    assert res["cells"]["NAND2_X1"] == 3
    assert res["cells"]["DFF_X1"] == 1
    assert res["cells"]["DLH_X1"] == 1
    assert res["latches_found"] == 1
    assert pys.generate_verdict(res).startswith("FAIL")


def test_run_lint_rejects_unsafe_define_and_include(tmp_path: Path) -> None:
    run_lint = SKILLS_DIR / "rat-init-project" / "templates" / "run_lint.sh"
    (tmp_path / "top.sv").write_text("module top; endmodule\n")
    res = run_script(run_lint, "--tool", "verilator", "-D", "A=1;touch pwned", "top.sv", cwd=tmp_path)
    assert res.returncode != 0
    assert not (tmp_path / "pwned").exists()


def test_run_syn_writes_syn_result_json_on_tool_failure(tmp_path: Path) -> None:
    run_syn = SKILLS_DIR / "rat-init-project" / "templates" / "run_syn.sh"
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "top.sv").write_text("module top; endmodule\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    yosys = fake_bin / "yosys"
    yosys.write_text("#!/usr/bin/env bash\necho 'ERROR: syntax error'\nexit 2\n")
    yosys.chmod(0o755)
    outdir = tmp_path / "syn_out"
    res = run_script(
        run_syn, "--tool", "yosys", "--top", "top", "--outdir", str(outdir), "rtl/top.sv",
        cwd=tmp_path, env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
    )
    assert res.returncode == 2
    syn_json = outdir / "rpt" / "syn_result.json"
    assert syn_json.is_file()
    payload = json.loads(syn_json.read_text())
    assert payload["exit_code"] == 2
    assert payload["tool"] == "yosys"


def test_compare_output_all_skipped_mandatory_is_inconclusive(tmp_path: Path) -> None:
    sys.path.insert(0, str(SKILLS_DIR / "codec-conformance-eval" / "scripts"))
    import compare_output as co

    results_json = tmp_path / "results.json"
    results_json.write_text(json.dumps([
        {
            "stream_name": "stream_a",
            "source_id": "src1",
            "source_priority": "mandatory",
            "status": "success",
            "output_path": str(tmp_path / "out.yuv"),
        }
    ]))
    (tmp_path / "out.yuv").write_bytes(b"\x00" * 16)
    golden_dir = tmp_path / "golden"
    golden_dir.mkdir()
    (golden_dir / "stream_a.yuv").write_bytes(b"\x00" * 16)
    cfg = {"golden": {"path": str(golden_dir), "comparison_mode": "psnr-threshold"}, "target": {}}
    metrics = co.compare_results(str(results_json), cfg)
    assert metrics["overall_verdict"] == "INCONCLUSIVE"
    assert metrics["summary"]["mandatory"]["total"] == 1
    assert metrics["source_breakdown"]["src1"]["skip"] == 1


def test_extract_module_doc_nested_param_parens() -> None:
    sys.path.insert(0, str(SKILLS_DIR / "rtl-document" / "scripts"))
    import extract_module_doc as emd

    sv = (
        "module nested_fifo #(\n"
        "  parameter int DEPTH = 16,\n"
        "  parameter int ADDR_W = $clog2(DEPTH)\n"
        ") (\n"
        "  input logic sys_clk,\n"
        "  input logic [ADDR_W-1:0]\n"
        "    i_addr,\n"
        "  output logic o_full\n"
        ");\nendmodule\n"
    )
    flattened = emd._flatten_port_block(sv)
    assert "i_addr" in flattened
    assert "o_full" in flattened
    assert "ADDR_W = $clog2" not in flattened


def test_compute_delta_handles_null_or_zero_targets() -> None:
    sys.path.insert(0, str(SKILLS_DIR / "rtl-ppa-optimize-dc" / "scripts"))
    import compute_delta as cd

    prev = {"timing": {"wns_ns": -0.1}, "power": {"total_mw": 100.0}, "area": {"total_um2": 1000.0}}
    curr = {"timing": {"wns_ns": -0.05}, "power": {"total_mw": 90.0}, "area": {"total_um2": 950.0}}
    targets = {"timing_slack_ns": None, "power_mw": 0, "area_um2": None}
    weights = {"timing": 0.7, "power": 0.2, "area": 0.1}
    delta = cd.weighted_delta(curr, prev, targets, weights)
    assert delta > 0
    met = cd.targets_met(curr, targets)
    assert isinstance(met["area"], bool)


def test_vcd_diff_aliases_and_no_common_signals(tmp_path: Path) -> None:
    sys.path.insert(0, str(SKILLS_DIR / "rtl-bug-repro" / "scripts"))
    import vcd_diff

    vcd1 = tmp_path / "a.vcd"
    vcd1.write_text(
        "$scope module top $end\n"
        "$var wire 1 ! sig_a $end\n"
        "$var wire 1 ! sig_b $end\n"
        "$upscope $end\n"
        "$enddefinitions $end\n"
        "#0\n0!\n#10\n1!\n"
    )
    parsed = vcd_diff.parse_vcd_signals(str(vcd1))
    assert "top.sig_a" in parsed and "top.sig_b" in parsed
    assert parsed["top.sig_a"] == parsed["top.sig_b"]

    vcd2 = tmp_path / "b.vcd"
    vcd2.write_text(
        "$scope module other $end\n$var wire 1 # unrelated $end\n$upscope $end\n$enddefinitions $end\n#0\n0#\n"
    )
    res = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "rtl-bug-repro" / "scripts" / "vcd_diff.py"), str(vcd1), str(vcd2)],
        capture_output=True, text=True,
    )
    assert res.returncode == 2
    assert "INCONCLUSIVE" in res.stdout


def test_compare_3way_rejects_empty_and_malformed_files(tmp_path: Path) -> None:
    script = SKILLS_DIR / "rtl-model-consistency" / "scripts" / "compare_3way.py"
    a = tmp_path / "a.hex"
    b = tmp_path / "b.hex"
    c = tmp_path / "c.hex"
    for p in (a, b, c):
        p.write_text("")
    r_empty = subprocess.run(
        [sys.executable, str(script), "--refc", str(a), "--bfm", str(b), "--rtl", str(c)],
        capture_output=True, text=True,
    )
    assert r_empty.returncode == 2

    a.write_text("NOT_HEX\n")
    b.write_text("NOT_HEX\n")
    c.write_text("NOT_HEX\n")
    r_bad = subprocess.run(
        [sys.executable, str(script), "--refc", str(a), "--bfm", str(b), "--rtl", str(c)],
        capture_output=True, text=True,
    )
    assert r_bad.returncode == 2


def test_rat_doctor_handles_invalid_default_site_and_backend(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "config.json").write_text(json.dumps({
        "schema_version": 1,
        "default_site": "../../etc/passwd",
        "execution": {"backend": "bogus-backend"},
    }))
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "rat_doctor.py"), "--root", str(tmp_path), "--json"],
        capture_output=True, text=True,
        env={**os.environ, "CLAUDE_PLUGIN_DATA": str(data_dir)},
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert isinstance(report, list) and len(report) > 0
    assert all("item" in row and "status" in row for row in report)
