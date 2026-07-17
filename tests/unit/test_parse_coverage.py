"""Tests for skills/rtl-p5s-coverage-analyze/scripts/parse_coverage.py.

Covers both input formats the rtl-p5s-func-verify pipeline produces
(lcov .info from merge_coverage.sh, raw Verilator coverage.dat), the
committed worked-example regeneration sync, verdict logic vs project
targets, deterministic uncovered-bin ranking, and error handling.

All script invocations go through subprocess so the argparse CLI surface
is exercised exactly as the skill documents it.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "rtl-p5s-coverage-analyze"
SCRIPT = SKILL_DIR / "scripts" / "parse_coverage.py"
EXAMPLES = SKILL_DIR / "examples"


def run_script(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=cwd, check=False)


def load_json(path):
    return json.loads(Path(path).read_text())


# ---------------------------------------------------------------------------
# Committed example regeneration sync (mandatory pattern)
# ---------------------------------------------------------------------------

class TestExampleRegenerationSync:
    def test_lcov_example_json_matches_regeneration(self, tmp_path):
        out = tmp_path / "regen.json"
        result = run_script("merged.info", "-o", out, cwd=EXAMPLES)
        assert result.returncode == 1, result.stderr  # overall FAIL by design
        committed = (EXAMPLES / "merged_coverage.json").read_text()
        assert out.read_text() == committed

    def test_dat_example_json_matches_regeneration(self, tmp_path):
        out = tmp_path / "regen.json"
        result = run_script("coverage.dat", "-o", out, cwd=EXAMPLES)
        assert result.returncode == 1, result.stderr  # overall FAIL by design
        committed = (EXAMPLES / "dat_coverage.json").read_text()
        assert out.read_text() == committed

    def test_output_is_deterministic_across_runs(self, tmp_path):
        outs = []
        for name in ("a.json", "b.json"):
            out = tmp_path / name
            run_script("coverage.dat", "-o", out, cwd=EXAMPLES)
            outs.append(out.read_text())
        assert outs[0] == outs[1]


# ---------------------------------------------------------------------------
# lcov .info parsing
# ---------------------------------------------------------------------------

class TestLcov:
    def test_summary_and_verdicts(self):
        doc = load_json(EXAMPLES / "merged_coverage.json")
        assert doc["format"] == "lcov"
        m = doc["summary"]["metrics"]
        assert m["line"] == {"covered": 16, "total": 20, "pct": 80.0,
                             "target_pct": 90.0, "verdict": "FAIL"}
        # No toggle/fsm data in lcov → N/A, never fabricated.
        for metric in ("toggle", "fsm"):
            assert m[metric]["total"] == 0
            assert m[metric]["pct"] is None
            assert m[metric]["verdict"] == "N/A"
        assert doc["summary"]["overall_verdict"] == "FAIL"
        assert doc["summary"]["files_total"] == 2

    def test_per_file_percentages(self):
        doc = load_json(EXAMPLES / "merged_coverage.json")
        by_file = {f["file"]: f["metrics"] for f in doc["files"]}
        assert by_file["rtl/pixel_fifo/pixel_fifo.sv"]["line"]["pct"] == 90.0
        assert by_file["rtl/pixel_ctrl/pixel_ctrl.sv"]["line"]["pct"] == 70.0

    def test_uncovered_ranked_by_file_then_line(self):
        doc = load_json(EXAMPLES / "merged_coverage.json")
        entries = [(u["rank"], u["file"], u["line"]) for u in doc["uncovered"]]
        assert entries == [
            (1, "rtl/pixel_ctrl/pixel_ctrl.sv", 33),
            (2, "rtl/pixel_ctrl/pixel_ctrl.sv", 35),
            (3, "rtl/pixel_ctrl/pixel_ctrl.sv", 38),
            (4, "rtl/pixel_fifo/pixel_fifo.sv", 44),
        ]

    def test_brda_records_feed_branch_metric(self, tmp_path):
        info = tmp_path / "cov.info"
        info.write_text(
            "TN:t\nSF:a.sv\nDA:1,1\nBRDA:5,0,0,3\nBRDA:5,0,1,0\n"
            "BRDA:5,0,2,-\nend_of_record\n")
        out = tmp_path / "out.json"
        result = run_script(info, "-o", out, "--target-line", "50")
        assert result.returncode == 0, result.stderr
        doc = load_json(out)
        branch = doc["summary"]["metrics"]["branch"]
        assert branch == {"covered": 1, "total": 3, "pct": 33.33,
                          "target_pct": None, "verdict": "N/A"}
        details = {u["detail"] for u in doc["uncovered"]}
        assert details == {"block 0 branch 1", "block 0 branch 2"}

    def test_target_branch_flag_enables_branch_verdict(self, tmp_path):
        info = tmp_path / "cov.info"
        info.write_text("TN:t\nSF:a.sv\nBRDA:5,0,0,3\nBRDA:5,0,1,0\nend_of_record\n")
        out = tmp_path / "out.json"
        result = run_script(info, "-o", out, "--target-branch", "70")
        assert result.returncode == 1
        doc = load_json(out)
        assert doc["summary"]["metrics"]["branch"]["verdict"] == "FAIL"

    def test_target_override_flips_verdict(self, tmp_path):
        out = tmp_path / "out.json"
        result = run_script(EXAMPLES / "merged.info", "-o", out,
                            "--target-line", "80")
        assert result.returncode == 0, result.stderr
        doc = load_json(out)
        assert doc["summary"]["metrics"]["line"]["verdict"] == "PASS"
        assert doc["summary"]["overall_verdict"] == "PASS"

    def test_da_before_sf_is_error(self, tmp_path):
        info = tmp_path / "bad.info"
        info.write_text("TN:t\nDA:1,1\n")
        result = run_script(info, "--format", "lcov")
        assert result.returncode == 2
        assert "before any SF record" in result.stderr


# ---------------------------------------------------------------------------
# Verilator coverage.dat parsing
# ---------------------------------------------------------------------------

class TestVerilatorDat:
    def test_metric_mapping_and_verdicts(self):
        doc = load_json(EXAMPLES / "dat_coverage.json")
        assert doc["format"] == "dat"
        m = doc["summary"]["metrics"]
        assert m["line"] == {"covered": 9, "total": 10, "pct": 90.0,
                             "target_pct": 90.0, "verdict": "PASS"}
        assert m["toggle"] == {"covered": 8, "total": 10, "pct": 80.0,
                               "target_pct": 80.0, "verdict": "PASS"}
        # v_user points count as the fsm metric (documented mapping).
        assert m["fsm"] == {"covered": 2, "total": 3, "pct": 66.67,
                            "target_pct": 70.0, "verdict": "FAIL"}
        # branch informational without --target-branch.
        assert m["branch"]["pct"] == 75.0
        assert m["branch"]["verdict"] == "N/A"
        assert doc["summary"]["overall_verdict"] == "FAIL"

    def test_uncovered_ranking_priority_fsm_branch_line_toggle(self):
        doc = load_json(EXAMPLES / "dat_coverage.json")
        metrics_in_order = [u["metric"] for u in doc["uncovered"]]
        assert metrics_in_order == ["fsm", "branch", "line", "toggle", "toggle"]
        assert doc["uncovered"][0]["detail"].startswith("fsm_state DRAIN->IDLE")
        assert doc["uncovered"][0]["rank"] == 1

    def test_detail_carries_comment_and_hierarchy(self):
        doc = load_json(EXAMPLES / "dat_coverage.json")
        assert all("@ top.u_fifo" in u["detail"] for u in doc["uncovered"])

    def test_min_count_reclassifies_low_hit_bins(self, tmp_path):
        out = tmp_path / "out.json"
        result = run_script(EXAMPLES / "coverage.dat", "-o", out,
                            "--min-count", "3")
        assert result.returncode == 1, result.stderr
        doc = load_json(out)
        # Bins with count 2 (lines 38/41, one branch, o_full/o_empty toggles,
        # one fsm point) now count as uncovered.
        assert doc["summary"]["metrics"]["line"]["covered"] == 7
        assert doc["summary"]["uncovered_total"] > 5

    def test_max_uncovered_caps_list_but_not_total(self, tmp_path):
        out = tmp_path / "out.json"
        result = run_script(EXAMPLES / "coverage.dat", "-o", out,
                            "--max-uncovered", "2")
        assert result.returncode == 1, result.stderr
        doc = load_json(out)
        assert len(doc["uncovered"]) == 2
        assert doc["summary"]["uncovered_total"] == 5
        assert [u["rank"] for u in doc["uncovered"]] == [1, 2]

    def test_unknown_page_types_are_skipped_not_miscounted(self, tmp_path):
        dat = tmp_path / "cov.dat"
        dat.write_text(
            "# SystemC::Coverage-3\n"
            "C '\x01f\x02a.sv\x01l\x021\x01page\x02v_line/a\x01o\x02x' 1\n"
            "C '\x01f\x02a.sv\x01l\x022\x01page\x02v_mystery/a\x01o\x02y' 0\n")
        out = tmp_path / "out.json"
        result = run_script(dat, "-o", out, "--target-line", "50")
        assert result.returncode == 0, result.stderr
        doc = load_json(out)
        totals = {k: v["total"] for k, v in doc["summary"]["metrics"].items()}
        assert totals == {"line": 1, "toggle": 0, "fsm": 0, "branch": 0}

    def test_malformed_dat_entry_is_error(self, tmp_path):
        dat = tmp_path / "cov.dat"
        dat.write_text("# SystemC::Coverage-3\nC broken-line\n")
        result = run_script(dat)
        assert result.returncode == 2
        assert "unrecognized coverage.dat entry" in result.stderr


# ---------------------------------------------------------------------------
# Format detection and error handling
# ---------------------------------------------------------------------------

class TestCliContract:
    def test_autodetect_dat_by_header_despite_info_extension(self, tmp_path):
        weird = tmp_path / "renamed.info"
        weird.write_text((EXAMPLES / "coverage.dat").read_text())
        out = tmp_path / "out.json"
        result = run_script(weird, "-o", out)
        assert result.returncode == 1, result.stderr
        assert load_json(out)["format"] == "dat"

    def test_explicit_format_overrides_autodetect(self, tmp_path):
        result = run_script(EXAMPLES / "merged.info", "--format", "dat")
        assert result.returncode == 2  # lcov records are not valid dat entries

    def test_missing_input_is_error(self, tmp_path):
        result = run_script(tmp_path / "nope.info")
        assert result.returncode == 2
        assert "not found" in result.stderr
        assert "do not fabricate" in result.stderr

    def test_undetectable_format_is_error(self, tmp_path):
        f = tmp_path / "mystery.txt"
        f.write_text("hello world\n")
        result = run_script(f)
        assert result.returncode == 2
        assert "cannot auto-detect format" in result.stderr

    def test_empty_records_is_error_not_empty_report(self, tmp_path):
        f = tmp_path / "empty.info"
        f.write_text("TN:t\n")
        result = run_script(f, "--format", "lcov")
        assert result.returncode == 2
        assert "no coverage records found" in result.stderr

    def test_stdout_mode_emits_json(self):
        result = run_script(EXAMPLES / "merged.info")
        assert result.returncode == 1
        doc = json.loads(result.stdout)
        assert doc["tool"] == "parse_coverage.py"

    def test_no_timestamps_in_output(self):
        for name in ("merged_coverage.json", "dat_coverage.json"):
            text = (EXAMPLES / name).read_text()
            assert "timestamp" not in text
