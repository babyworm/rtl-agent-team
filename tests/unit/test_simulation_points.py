"""Simulation closure uses the planned inventory and measurements from selected runs."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT


@pytest.fixture(autouse=True)
def _initialized_project(tmp_path):
    # P5 closure runs in an initialized project; its run records live under .rat/.
    (tmp_path / ".rat").mkdir()


def cli(script, *args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script), *map(str, args)],
        capture_output=True, text=True, timeout=15,
    )


def point(point_id, kind, **fields):
    return {
        "id": point_id, "kind": kind, "requirement": "REQ-F-001",
        "source": "refc/clip.c#clip", "trigger": "input exceeds 255",
        "expected_result": "output clamps to 255",
        "confidence": "high", "basis": "The model saturates in its upper branch.",
        **fields,
    }


def plan(root, *points):
    model = root / "refc/clip.c"
    model.parent.mkdir(exist_ok=True)
    if not model.exists():
        model.write_text("int clip(int x) { return x > 255 ? 255 : x; }\n")
    path = root / "sim/verification-points.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"points": points}))


def run_record(root, name, records, *, compile_output="", seed_logs=(), legacy=False, fails=False):
    source = root / "clip.sv"
    if not source.exists():
        source.write_text("module clip; endmodule\n")
    out = root / "sim" / name
    out.mkdir()
    begin = cli("verify_evidence.py", "begin", "--root", root, "--outdir", out, "--source", source,
                "--tool", "iverilog", "--top", "clip", "--context", "uvm:clip" if seed_logs else "")
    assert begin.returncode == 0, begin.stderr
    snapshot = Path(begin.stdout.strip())
    log = out / "runtime.log"
    seed_args = []
    if seed_logs:
        with log.open("wb") as aggregate:
            for seed, text in enumerate(seed_logs):
                path = out / f"seed_{seed}/sim.log"
                path.parent.mkdir()
                path.write_text(text + "\nRAT_SIM_PASS\n")
                aggregate.write(path.read_bytes())
                if not legacy:
                    seed_args.extend(("--seed-log", path))
    else:
        log.write_text(records + "\nRAT_SIM_PASS\n")
    combined = out / "combined.log"
    combined.write_text(compile_output + log.read_text())
    finish = cli("verify_evidence.py", "finish", "--snapshot", snapshot, "--exit-code", 0,
                 "--log", combined, "--runtime-log", log, *seed_args)
    assert (finish.returncode != 0) == fails, finish.stdout + finish.stderr
    return snapshot.stem


def close(root, *runs):
    judgment = root / "docs/phase-5-verify/judgment.json"
    judgment.parent.mkdir(parents=True, exist_ok=True)
    judgment.write_text(json.dumps({"simulation_runs": runs}))
    return cli("gates/simulation_points.py", "--root", root)


def test_named_bin_and_checks_accumulate_across_selected_runs(tmp_path):
    plan(tmp_path, point("clip.upper", "coverpoint", minimum_hits=2),
         point("clip.stable", "assertion"), point("clip.compare", "scoreboard"))
    records = "RAT_COV_BIN clip.upper 1 2\nRAT_COV_END 1\nRAT_CHECK_POINT clip.stable 1 0\n"
    seed1 = run_record(tmp_path, "seed1", records + "RAT_CHECK_POINT clip.compare 0 0")
    seed2 = run_record(tmp_path, "seed2", records + "RAT_CHECK_POINT clip.compare 1 0")
    insufficient = close(tmp_path, seed1)
    assert insufficient.returncode != 0
    assert "clip.upper" in insufficient.stdout
    assert close(tmp_path, seed1, seed1).returncode != 0
    both = close(tmp_path, seed1, seed2)
    assert both.returncode == 0, both.stdout + both.stderr


@pytest.mark.parametrize(("kind", "records"), [
    ("coverpoint", "RAT_COV_BIN other 1 1\nRAT_COV_END 1"),
    ("assertion", "RAT_CHECK_POINT clip.upper 0 0"),
    ("scoreboard", "RAT_COV_BIN clip.upper 1 1\nRAT_COV_END 1"),
])
def test_passing_summary_cannot_cover_missing_vacuous_or_failing_point(tmp_path, kind, records):
    plan(tmp_path, point("clip.upper", kind))
    seed = run_record(tmp_path, "seed", records, compile_output="RAT_CHECK_POINT clip.upper 1 0\n")
    result = close(tmp_path, seed)
    assert result.returncode != 0, result.stdout
    assert "clip.upper" in result.stdout


def test_failure_in_legacy_passing_snapshot_still_blocks_closure(tmp_path):
    plan(tmp_path, point("clip.upper", "scoreboard"))
    seed = run_record(tmp_path, "seed", "RAT_CHECK_POINT clip.upper 5 1", fails=True)
    index = tmp_path / ".rat/state/verify-evidence.json"
    evidence = json.loads(index.read_text())
    evidence["runs"][0]["verdict"] = "PASS"
    index.write_text(json.dumps(evidence))
    result = close(tmp_path, seed)
    assert result.returncode != 0 and "clip.upper" in result.stdout


def test_reachability_is_explicit_and_each_outcome_needs_its_own_check(tmp_path):
    iron = tmp_path / "docs/phase-3-uarch/iron-requirements.json"
    iron.parent.mkdir(parents=True)
    iron.write_text(json.dumps([{"acceptance_criteria": [
        {"ac_id": "AC-limit", "test_method": "cocotb"},
        {"ac_id": "AC-request", "test_method": "coverpoint"},
        {"ac_id": "AC-stall", "test_method": "assertion"},
    ]}]))
    limit_bin = point("clip.upper", "coverpoint", requirement="AC-limit")
    request = point("request", "coverpoint", requirement="AC-request")
    stall = point("stall", "assertion", requirement="AC-stall")
    plan(tmp_path, limit_bin, request, stall)
    records = "RAT_COV_BIN clip.upper 1 1\nRAT_COV_BIN request 1 1\nRAT_COV_END 2\nRAT_CHECK_POINT stall 1 0"
    old = run_record(tmp_path, "before_comparison", records)
    rejected = close(tmp_path, old)
    assert rejected.returncode != 0 and "AC-limit: missing assertion or scoreboard" in rejected.stdout

    compare = point("clip.compare", "scoreboard", requirement="AC-limit")
    plan(tmp_path, limit_bin, request, stall, compare)
    new = run_record(tmp_path, "comparison", "RAT_CHECK_POINT clip.compare 1 0")
    assert close(tmp_path, old, new).returncode == 0
    plan(tmp_path, limit_bin, {**request, "kind": "assertion"}, stall, compare)
    rejected = close(tmp_path, old, new)
    assert rejected.returncode != 0 and "AC-request: missing coverpoint" in rejected.stdout


@pytest.mark.parametrize("legacy", [True, False])
def test_repeated_bin_summary_counts_only_across_real_seed_logs(tmp_path, legacy):
    plan(tmp_path, point("clip.upper", "coverpoint", minimum_hits=2), point("clip.compare", "scoreboard"))
    sample = "RAT_COV_BIN clip.upper 1 2\nRAT_COV_END 1\nRAT_CHECK_POINT clip.compare 1 0"
    bad = run_record(tmp_path, "one", "", seed_logs=[sample + "\nRAT_SIM_PASS\n" + sample], legacy=legacy)
    assert close(tmp_path, bad).returncode != 0
    good = run_record(tmp_path, "two", "", seed_logs=[sample, sample], legacy=legacy)
    result = close(tmp_path, good)
    assert result.returncode == 0 and "2/2 hits" in result.stdout
    # For new records the verified aggregate alone preserves both seed boundaries.
    (tmp_path / "sim/two/seed_0/sim.log").unlink()
    assert (close(tmp_path, good).returncode != 0) == legacy


def test_reuse_raw_bin_counts_after_changing_minimum(tmp_path):
    bin_point, compare = point("clip.upper", "coverpoint"), point("clip.compare", "scoreboard")
    plan(tmp_path, bin_point, compare)
    seed = run_record(tmp_path, "old", "RAT_COV_BIN clip.upper 7 1\nRAT_COV_END 1\nRAT_CHECK_POINT clip.compare 1 0")
    plan(tmp_path, {**bin_point, "minimum_hits": 5}, compare)
    result = close(tmp_path, seed)
    assert result.returncode == 0 and "7/5 hits" in result.stdout
    plan(tmp_path, {**bin_point, "minimum_hits": 8}, compare)
    assert close(tmp_path, seed).returncode != 0
    more = run_record(tmp_path, "new", "RAT_COV_BIN clip.upper 1 8\nRAT_COV_END 1")
    assert close(tmp_path, seed, more).returncode == 0


@pytest.mark.parametrize("change", ["clip.sv", "sim/seed/runtime.log", "sim/seed/combined.log"])
def test_changed_inputs_or_logs_invalidate_point_evidence(tmp_path, change):
    plan(tmp_path, point("clip.compare", "scoreboard"))
    seed = run_record(tmp_path, "seed", "RAT_CHECK_POINT clip.compare 1 0")
    assert close(tmp_path, seed).returncode == 0
    path = tmp_path / change
    if change.endswith(".sv"):
        path.write_text(path.read_text() + "// comment only\n")
        assert close(tmp_path, seed).returncode == 0
        path.write_text(path.read_text() + "wire changed;\n")
    else:
        path.write_text(path.read_text() + "\n")
    assert close(tmp_path, seed).returncode != 0


def test_plan_requires_unique_ids_and_resolution_of_low_confidence(tmp_path):
    item = point("clip.compare", "scoreboard", confidence="low",
                 basis="The model treats the maximum as exclusive, the spec uses inclusive bounds.")
    plan(tmp_path, item)
    gate = ("gates/simulation_points.py", "--root", tmp_path, "--plan-only")
    assert cli(*gate).returncode != 0
    item["resolution"] = "The owner confirmed the upper-bound behavior in REQ-F-001."
    plan(tmp_path, item)
    assert cli(*gate).returncode == 0
    plan(tmp_path, item, item)
    assert cli(*gate).returncode != 0


@pytest.mark.parametrize(("field", "updated"), [
    ("trigger", "input equals 255"), ("expected_result", "output wraps to zero"),
])
def test_changed_point_meaning_requires_new_measurement(tmp_path, field, updated):
    item = point("clip.compare", "scoreboard")
    plan(tmp_path, item)
    seed = run_record(tmp_path, "seed", "RAT_CHECK_POINT clip.compare 1 0")
    assert close(tmp_path, seed).returncode == 0
    plan(tmp_path, {**item, field: updated})
    assert close(tmp_path, seed).returncode != 0


def test_changed_reference_vectors_invalidate_measurements(tmp_path):
    vectors = tmp_path / "golden.txt"
    vectors.write_text("256 -> 255\n")
    plan(tmp_path, point("clip.compare", "scoreboard", inputs=["golden.txt"]))
    seed = run_record(tmp_path, "seed", "RAT_CHECK_POINT clip.compare 1 0")
    assert close(tmp_path, seed).returncode == 0
    vectors.write_text("256 -> 0\n")
    assert close(tmp_path, seed).returncode != 0


def test_unchanged_point_reuses_run_after_new_point_is_added(tmp_path):
    original = point("clip.upper", "coverpoint")
    plan(tmp_path, original)
    seed1 = run_record(tmp_path, "bound", "RAT_COV_BIN clip.upper 1 1\nRAT_COV_END 1")
    original["basis"] = "The updated review cites clip() and vector 256."
    plan(tmp_path, original, point("clip.compare", "scoreboard"))
    seed2 = run_record(tmp_path, "compare", "RAT_CHECK_POINT clip.compare 1 0")
    result = close(tmp_path, seed1, seed2)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("wrapper", ["requirements", "iron_requirements", None])
def test_p3_selected_simulation_criteria_have_an_exact_point(tmp_path, wrapper):
    first, sibling = "REQ-U-01.AC-10", "REQ-U-01.AC-1"
    criteria = [
        {"ac_id": first, "test_method": "cocotb", "verifiable": True},
        {"ac_id": sibling, "test_method": "assertion", "verifiable": True},
        {"ac_id": "AC-3", "test_method": "formal"},
        {"ac_id": "AC-4", "test_method": "inspection"},
        {"ac_id": "AC-5", "test_method": "cocotb", "verifiable": False},
        "a legacy free-form criterion",
    ]
    requirements = [{"id": "REQ-U-01", "acceptance_criteria": criteria}]
    iron = tmp_path / "docs/phase-3-uarch/iron-requirements.json"
    iron.parent.mkdir(parents=True)
    iron.write_text(json.dumps({wrapper: requirements} if wrapper else requirements))

    first_point = point("clip.compare", "scoreboard", requirement=first)
    plan(tmp_path, first_point)
    seed = run_record(tmp_path, "seed", "RAT_CHECK_POINT clip.compare 1 0")
    result = close(tmp_path, seed)
    assert result.returncode != 0 and sibling in result.stdout

    gate = ("gates/simulation_points.py", "--root", tmp_path, "--plan-only")
    plan(tmp_path, first_point, point("clip.stable", "coverpoint", requirement=sibling))
    assert cli(*gate).returncode != 0
    plan(tmp_path, first_point, point("clip.stable", "assertion", requirement=sibling))
    assert cli(*gate).returncode == 0
    fixed = run_record(tmp_path, "fixed", "RAT_CHECK_POINT clip.stable 1 0")
    assert close(tmp_path, seed, fixed).returncode == 0


def test_hit_bins_without_a_behavioral_outcome_cannot_close_simulation(tmp_path):
    plan(tmp_path, point("clip.upper", "coverpoint"))
    assert cli("gates/simulation_points.py", "--root", tmp_path, "--plan-only").returncode == 0
    seed = run_record(tmp_path, "seed", "RAT_COV_BIN clip.upper 1 1\nRAT_COV_END 1")
    result = close(tmp_path, seed)
    checks = json.loads(result.stdout)["checks"]
    assert result.returncode != 0
    assert any(c["check"] == "simulation point clip.upper" and c["passed"] for c in checks)
    assert any(c["check"] == "functional simulation outcome" and not c["passed"] for c in checks)


def test_p5_handoff_needs_measured_points_even_with_a_passing_report(tmp_path):
    report = tmp_path / "reviews/phase-5-verify/final-compliance.md"
    report.parent.mkdir(parents=True)
    report.write_text("Verdict: PASS")
    judgment = tmp_path / "docs/phase-5-verify/judgment.json"
    judgment.parent.mkdir(parents=True)
    summary = {"confidence": "high", "material_ambiguities": [],
               "verification_items": [{"id": "clip.compare", "requirement": "REQ-F-001",
                                       "expected_result": "output clamps to 255"}]}
    judgment.write_text(json.dumps(summary))
    gate = ("gates/phase_gate.py", "--root", tmp_path, "--phase")
    assert cli(*gate, 5).returncode != 0
    plan(tmp_path, point("clip.compare", "scoreboard"))
    run = run_record(tmp_path, "seed", "RAT_CHECK_POINT clip.compare 3 0")
    del summary["verification_items"]  # The simulation oracle already lives in the plan.
    judgment.write_text(json.dumps({**summary, "simulation_runs": [run]}))
    assert cli(*gate, 5).returncode == 0
    assert cli(*gate, 6, "--entry").returncode == 0
    (tmp_path / "sim/verification-points.json").unlink()
    assert cli(*gate, 6, "--entry").returncode != 0
