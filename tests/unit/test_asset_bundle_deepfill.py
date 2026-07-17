"""Deep-fill validation for asset-bundle scripts and examples.

Covers the follow-up work deferred by the 2026-05-13 asset-bundle clone-pack
plan: `gen_ipxact.py` (rtl-ipxact-gen), `parse_perf_report.py`
(rtl-p5s-perf-verify), and the worked examples/ content for rtl-bug-repro,
rtl-ipxact-gen, rtl-p5s-perf-verify, rtl-model-consistency, and
rtl-ip-instantiate.

All script invocations go through subprocess so the argparse CLI surface is
exercised exactly as the skills document it.
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"

IPXACT_DIR = SKILLS_DIR / "rtl-ipxact-gen"
PERF_DIR = SKILLS_DIR / "rtl-p5s-perf-verify"
GEN_IPXACT = IPXACT_DIR / "scripts" / "gen_ipxact.py"
PARSE_PERF = PERF_DIR / "scripts" / "parse_perf_report.py"

IPXACT_NS = {"ipxact": "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"}

# examples/ dirs deep-filled in this follow-up: must carry real content,
# not a bare .gitkeep placeholder.
DEEPFILLED_EXAMPLE_SKILLS = [
    "rtl-bug-repro",
    "rtl-ipxact-gen",
    "rtl-p5s-perf-verify",
    "rtl-model-consistency",
    "rtl-ip-instantiate",
]


def run_script(script, *args, cwd=None):
    """Run a skill script via subprocess; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=cwd, check=False)


# ---------------------------------------------------------------------------
# gen_ipxact.py
# ---------------------------------------------------------------------------

class TestGenIpxact:
    def test_example_sv_produces_well_formed_xml(self, tmp_path):
        out = tmp_path / "pixel_fifo.xml"
        result = run_script(GEN_IPXACT, IPXACT_DIR / "examples" / "pixel_fifo.sv",
                            "-o", out, "--vendor", "rtl_team",
                            "--library", "video_lib")
        assert result.returncode == 0, result.stderr
        root = ET.parse(out).getroot()
        assert root.tag == f"{{{IPXACT_NS['ipxact']}}}component"

    def test_vlnv_fields(self, tmp_path):
        out = tmp_path / "out.xml"
        run_script(GEN_IPXACT, IPXACT_DIR / "examples" / "pixel_fifo.sv",
                   "-o", out, "--vendor", "rtl_team", "--library", "video_lib")
        root = ET.parse(out).getroot()
        assert root.findtext("ipxact:vendor", namespaces=IPXACT_NS) == "rtl_team"
        assert root.findtext("ipxact:library", namespaces=IPXACT_NS) == "video_lib"
        assert root.findtext("ipxact:name", namespaces=IPXACT_NS) == "pixel_fifo"
        assert root.findtext("ipxact:version", namespaces=IPXACT_NS) == "1.0"

    def test_ports_directions_and_expression_widths(self, tmp_path):
        out = tmp_path / "out.xml"
        run_script(GEN_IPXACT, IPXACT_DIR / "examples" / "pixel_fifo.sv", "-o", out)
        root = ET.parse(out).getroot()
        ports = {}
        for port in root.findall("ipxact:model/ipxact:ports/ipxact:port",
                                 IPXACT_NS):
            name = port.findtext("ipxact:name", namespaces=IPXACT_NS)
            wire = port.find("ipxact:wire", IPXACT_NS)
            ports[name] = {
                "direction": wire.findtext("ipxact:direction",
                                           namespaces=IPXACT_NS),
                "left": wire.findtext(
                    "ipxact:vectors/ipxact:vector/ipxact:left",
                    namespaces=IPXACT_NS),
            }
        assert len(ports) == 9
        # Verbatim names with prefix, direction from keyword
        assert ports["i_wr_data"]["direction"] == "in"
        assert ports["o_rd_data"]["direction"] == "out"
        assert ports["clk"]["direction"] == "in"
        # Parameterized widths preserved as expressions, not literals
        assert ports["i_wr_data"]["left"] == "DATA_WIDTH-1"
        assert ports["o_level"]["left"] == "$clog2(DEPTH)"
        # Scalar ports carry no vector
        assert ports["i_wr_valid"]["left"] is None

    def test_parameters_present(self, tmp_path):
        out = tmp_path / "out.xml"
        run_script(GEN_IPXACT, IPXACT_DIR / "examples" / "pixel_fifo.sv", "-o", out)
        root = ET.parse(out).getroot()
        params = {
            p.findtext("ipxact:name", namespaces=IPXACT_NS):
                p.findtext("ipxact:value", namespaces=IPXACT_NS)
            for p in root.findall("ipxact:parameters/ipxact:parameter",
                                  IPXACT_NS)
        }
        assert params == {"DATA_WIDTH": "8", "DEPTH": "16"}

    def test_no_bus_interfaces_emitted(self, tmp_path):
        """Bus classification is interpretive (agent-owned) — script must not fabricate it."""
        out = tmp_path / "out.xml"
        run_script(GEN_IPXACT, IPXACT_DIR / "examples" / "pixel_fifo.sv", "-o", out)
        root = ET.parse(out).getroot()
        assert root.find("ipxact:busInterfaces", IPXACT_NS) is None

    def test_committed_example_xml_matches_regeneration(self, tmp_path):
        """examples/pixel_fifo.xml must stay in sync with the generator."""
        out = tmp_path / "regen.xml"
        result = run_script(GEN_IPXACT, "pixel_fifo.sv", "-o", out,
                            "--vendor", "rtl_team", "--library", "video_lib",
                            cwd=IPXACT_DIR / "examples")
        assert result.returncode == 0, result.stderr
        committed = (IPXACT_DIR / "examples" / "pixel_fifo.xml").read_text()
        assert out.read_text() == committed

    def test_missing_module_is_error(self, tmp_path):
        src = tmp_path / "empty.sv"
        src.write_text("// no module here\n")
        result = run_script(GEN_IPXACT, src, "-o", tmp_path / "out.xml")
        assert result.returncode == 2
        assert "no module declaration" in result.stderr

    def test_missing_input_file_is_error(self, tmp_path):
        result = run_script(GEN_IPXACT, tmp_path / "nope.sv")
        assert result.returncode == 2
        assert "not found" in result.stderr

    def test_non_ansi_header_is_error(self, tmp_path):
        src = tmp_path / "old.sv"
        src.write_text("module old_style(a, b);\ninput a;\noutput b;\nendmodule\n")
        result = run_script(GEN_IPXACT, src, "-o", tmp_path / "out.xml")
        assert result.returncode == 2
        assert "non-ANSI" in result.stderr

    def test_ip_version_from_version_parameter(self, tmp_path):
        src = tmp_path / "versioned.sv"
        src.write_text(
            'module versioned #(parameter VERSION = "2.1") '
            "(input logic clk, input logic i_en, output logic o_q);\nendmodule\n")
        out = tmp_path / "out.xml"
        result = run_script(GEN_IPXACT, src, "-o", out)
        assert result.returncode == 0, result.stderr
        root = ET.parse(out).getroot()
        assert root.findtext("ipxact:version", namespaces=IPXACT_NS) == "2.1"


# ---------------------------------------------------------------------------
# parse_perf_report.py
# ---------------------------------------------------------------------------

EXAMPLE_LOG = PERF_DIR / "examples" / "cabac_encoder_perf_run.log"
EXAMPLE_BASELINE = PERF_DIR / "examples" / "perf_baseline.json"


class TestParsePerfReport:
    def run_example(self, tmp_path, **overrides):
        out = tmp_path / "perf.json"
        args = ["--log", EXAMPLE_LOG, "--baseline", EXAMPLE_BASELINE,
                "--clock-mhz", "200", "--bits-per-txn", "8", "-o", out]
        result = run_script(PARSE_PERF, *args, **overrides)
        return result, out

    def test_example_log_produces_expected_json(self, tmp_path):
        result, out = self.run_example(tmp_path)
        assert result.returncode == 0, result.stderr
        doc = json.loads(out.read_text())
        assert doc["module"] == "cabac_encoder"
        assert doc["overall_verdict"] == "PASS"
        m = doc["metrics"]
        assert set(m) == {"throughput_mbps", "latency_cycles", "stall_cycles_pct"}
        assert m["throughput_mbps"] == {"measured": 480.0, "expected": 500.0,
                                        "delta_pct": -4.0, "verdict": "PASS"}
        assert m["latency_cycles"] == {"measured": 12.0, "expected": 12,
                                       "delta_pct": 0.0, "verdict": "PASS"}
        assert m["stall_cycles_pct"] == {"measured": 8.4, "expected": 8.0,
                                         "delta_pct": 5.0, "verdict": "PASS"}

    def test_committed_example_json_matches_regeneration(self, tmp_path):
        _, out = self.run_example(tmp_path)
        regenerated = json.loads(out.read_text())
        committed = json.loads(
            (PERF_DIR / "examples" / "cabac_encoder_perf.json").read_text())
        regenerated.pop("run_timestamp")
        committed.pop("run_timestamp")
        assert regenerated == committed

    def test_deviation_over_threshold_fails_with_exit_1(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"blocks": [{
            "name": "cabac_encoder",
            "throughput_mbps": 500.0,
            "clock_cycles": 12,
            "stall_cycles_pct": 2.9,  # measured 8.4 → +190% → FAIL
        }]}))
        out = tmp_path / "perf.json"
        result = run_script(PARSE_PERF, "--log", EXAMPLE_LOG,
                            "--baseline", baseline, "--clock-mhz", "200",
                            "--bits-per-txn", "8", "-o", out)
        assert result.returncode == 1
        doc = json.loads(out.read_text())
        assert doc["overall_verdict"] == "FAIL"
        assert doc["metrics"]["stall_cycles_pct"]["verdict"] == "FAIL"
        assert doc["metrics"]["latency_cycles"]["verdict"] == "PASS"

    def test_missing_clock_flags_marks_throughput_na(self, tmp_path):
        out = tmp_path / "perf.json"
        result = run_script(PARSE_PERF, "--log", EXAMPLE_LOG,
                            "--baseline", EXAMPLE_BASELINE, "-o", out)
        assert result.returncode == 0, result.stderr
        doc = json.loads(out.read_text())
        assert doc["metrics"]["throughput_mbps"]["verdict"] == "N/A"
        assert doc["metrics"]["throughput_mbps"]["measured"] is None
        assert doc["overall_verdict"] == "PASS"  # remaining metrics still judged
        assert "throughput_mbps not computed" in doc["notes"]

    def test_missing_baseline_file_is_error(self, tmp_path):
        result = run_script(PARSE_PERF, "--log", EXAMPLE_LOG,
                            "--baseline", tmp_path / "nope.json")
        assert result.returncode == 2
        assert "baseline not found" in result.stderr

    def test_log_without_summary_block_is_error(self, tmp_path):
        log = tmp_path / "empty.log"
        log.write_text("Verilator: $finish\n")
        result = run_script(PARSE_PERF, "--log", log,
                            "--baseline", EXAMPLE_BASELINE)
        assert result.returncode == 2
        assert "no '=== Performance Summary" in result.stderr

    def test_unknown_baseline_block_yields_na_not_fabrication(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"blocks": [{"name": "other_block"}]}))
        out = tmp_path / "perf.json"
        result = run_script(PARSE_PERF, "--log", EXAMPLE_LOG,
                            "--baseline", baseline, "--clock-mhz", "200",
                            "--bits-per-txn", "8", "-o", out)
        assert result.returncode == 0, result.stderr
        doc = json.loads(out.read_text())
        assert doc["overall_verdict"] == "N/A"
        for metric in doc["metrics"].values():
            assert metric["expected"] is None
            assert metric["verdict"] == "N/A"


# ---------------------------------------------------------------------------
# examples/ deep-fill structural checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill_name", DEEPFILLED_EXAMPLE_SKILLS)
def test_examples_dir_has_real_content(skill_name):
    """Deep-filled examples/ must contain a README plus non-placeholder files."""
    examples = SKILLS_DIR / skill_name / "examples"
    files = [p for p in examples.rglob("*") if p.is_file()]
    names = {p.name for p in files}
    assert ".gitkeep" not in names, f"{skill_name}: stale .gitkeep placeholder"
    assert "README.md" in names, f"{skill_name}: examples/README.md missing"
    assert len(files) >= 2, f"{skill_name}: examples/ has no worked content"


def test_model_consistency_example_sets_are_self_consistent():
    """Consistent set must fully match; drift set must diverge only at RTL vector 11."""
    examples = SKILLS_DIR / "rtl-model-consistency" / "examples"

    def read_hex(path):
        return [int(line, 16) for line in path.read_text().splitlines()
                if line.strip() and not line.startswith("#")]

    consistent = {name: read_hex(examples / "outputs_consistent" / f"{name}_output.hex")
                  for name in ("ref", "bfm", "rtl")}
    assert consistent["ref"] == consistent["bfm"] == consistent["rtl"]
    assert len(consistent["ref"]) == 16

    drift = {name: read_hex(examples / "outputs_rtl_drift" / f"{name}_output.hex")
             for name in ("ref", "bfm", "rtl")}
    assert drift["ref"] == drift["bfm"]  # ref == BFM != RTL → "RTL has a bug"
    mismatches = [i for i, (a, b) in enumerate(zip(drift["ref"], drift["rtl"]))
                  if a != b]
    assert mismatches == [11]


def test_no_deep_fill_placeholders_remain_in_filled_skills():
    """SKILL.md Assets tables of the deep-filled rows must not advertise stubs."""
    for skill_name, asset in [
        ("rtl-ipxact-gen", "scripts/gen_ipxact.py"),
        ("rtl-p5s-perf-verify", "scripts/parse_perf_report.py"),
    ]:
        script = SKILLS_DIR / skill_name / asset
        assert "NotImplementedError" not in script.read_text(), (
            f"{skill_name}/{asset} is still a stub")
        skill_md = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        row = [ln for ln in skill_md.splitlines() if f"`{asset}`" in ln]
        assert row and "deep-fill" not in row[0], (
            f"{skill_name}/SKILL.md still marks {asset} as deep-fill pending")


class TestGroupedPortsIpxact:
    """Codex round-8 regression: grouped ANSI ports ('input logic [7:0] i_a,
    i_b') must keep vector metadata for every declarator; an explicit type
    without a range ('logic i_en') stays scalar."""

    def test_grouped_and_explicit_scalar(self, tmp_path):
        import subprocess
        import sys
        import xml.etree.ElementTree as ET
        from pathlib import Path

        script = (Path(__file__).resolve().parents[2]
                  / "skills" / "rtl-ipxact-gen" / "scripts" / "gen_ipxact.py")
        sv = tmp_path / "grp.sv"
        sv.write_text(
            "module grp (\n"
            "  input  logic clk,\n"
            "  input  logic [7:0] i_a, i_b,\n"
            "  input  logic i_en,\n"
            "  output logic [7:0] o_q\n"
            ");\nendmodule\n")
        out = tmp_path / "grp.xml"
        r = subprocess.run(
            [sys.executable, str(script), str(sv), "-o", str(out)],
            capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        ns = {"x": "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"}
        root = ET.parse(out).getroot()
        left_of = {}
        for p in root.findall(".//x:port", ns):
            nm = p.find("x:name", ns).text
            left = p.find(".//x:left", ns)
            left_of[nm] = left.text if left is not None else None
        assert left_of.get("i_a") == "7", left_of
        assert left_of.get("i_b") == "7", (
            f"i_b must inherit [7:0] from the grouped declaration: {left_of}")
        assert left_of.get("i_en") is None, (
            "explicit scalar type must not inherit the group range")

    def test_sign_qualifier_resets_group_range(self):
        """Codex round-9: 'input [7:0] i_a, signed i_b' — i_b is scalar."""
        import importlib.util
        from pathlib import Path

        script = (Path(__file__).resolve().parents[2]
                  / "skills" / "rtl-ipxact-gen" / "scripts" / "gen_ipxact.py")
        spec = importlib.util.spec_from_file_location("gx_r9", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ports = mod.parse_ports("input [7:0] i_a, signed i_b")
        by = {p["name"]: (p["left"], p["right"]) for p in ports}
        assert by["i_a"] == ("7", "0")
        assert by["i_b"] == (None, None), "sign qualifier must reset the range"
