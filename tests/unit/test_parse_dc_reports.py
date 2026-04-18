"""Unit tests for parse_dc_reports.py — DC .rpt → ppa-report.json."""
import json
import os
import pathlib
import sys
import textwrap

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "skills" / "rtl-ppa-optimize-dc" / "scripts"
FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "dc-reports"
sys.path.insert(0, str(SCRIPTS_DIR))

import parse_dc_reports as pdr  # noqa: E402


class TestParseArea:
    def test_totals(self):
        result = pdr.parse_area(FIXTURES / "area.rpt")
        assert result["total_um2"] == pytest.approx(45230.500034)
        assert result["combinational_um2"] == pytest.approx(28150.200012)
        assert result["sequential_um2"] == pytest.approx(17080.300022)
        assert result["buf_inv_um2"] == pytest.approx(2341.700001)
        assert result["macro_um2"] == pytest.approx(0.0)

    def test_hierarchical_breakdown(self):
        result = pdr.parse_area(FIXTURES / "area.rpt")
        hiers = [m["hier"] for m in result["per_module"]]
        assert "top/u_core" in hiers
        assert "top/u_core/u_s1" in hiers
        assert "top" not in hiers, "root 'top' row must be excluded from per_module"
        u_core = next(m for m in result["per_module"] if m["hier"] == "top/u_core")
        assert u_core["um2"] == pytest.approx(12345.6)
        assert u_core["pct"] == pytest.approx(27.30, rel=0.01)

    def test_hierarchical_breakdown_with_non_top_name(self, tmp_path):
        content = textwrap.dedent("""
        Total cell area:                 10000.0
        Combinational area:              6000.0
        Noncombinational area:           3500.0
        Buf/Inv area:                     500.0
        Macro/Black Box area:               0.0

        Hierarchical area distribution:
          vc_transform_8x8                       10000.0  100.00%
            vc_transform_8x8/u_core                4500.0   45.00%
            vc_transform_8x8/u_core/u_s1           2500.0   25.00%
            vc_transform_8x8/u_io                  1500.0   15.00%
        """)
        rpt = tmp_path / "area.rpt"
        rpt.write_text(content)
        result = pdr.parse_area(rpt)
        hiers = [m["hier"] for m in result["per_module"]]
        # Non-top root must be excluded (depth 0)
        assert "vc_transform_8x8" not in hiers
        # Child modules must be captured
        assert "vc_transform_8x8/u_core" in hiers
        assert "vc_transform_8x8/u_core/u_s1" in hiers
        assert "vc_transform_8x8/u_io" in hiers

    def test_missing_file_returns_empty(self):
        result = pdr.parse_area(None)
        assert result == {}


class TestParseTiming:
    def test_clock_and_period(self):
        result = pdr.parse_timing(FIXTURES / "timing.rpt")
        assert result["clock"] == "sys_clk"
        assert result["period_ns"] == pytest.approx(1.25)

    def test_wns(self):
        result = pdr.parse_timing(FIXTURES / "timing.rpt")
        assert result["wns_ns"] == pytest.approx(-0.083)

    def test_critical_paths(self):
        result = pdr.parse_timing(FIXTURES / "timing.rpt")
        assert len(result["critical_paths"]) >= 1
        worst = result["critical_paths"][0]
        assert "u_core/u_s1/pix_reg[7]" in worst["from"]
        assert "u_core/u_s2/sum_reg[15]" in worst["to"]
        assert worst["slack_ns"] == pytest.approx(-0.083)

    def test_tns_ns_cross_populated(self, tmp_path):
        # parse_timing alone doesn't know TNS; it's populated by run() from qor.
        out = tmp_path / "report.json"
        pdr.run(str(FIXTURES), str(out))
        data = json.loads(out.read_text())
        assert data["timing"]["tns_ns"] == pytest.approx(-2.410, rel=0.01)
        assert data["timing"]["num_violating_paths"] == 17


class TestParsePower:
    def test_total_power(self):
        result = pdr.parse_power(FIXTURES / "power.rpt")
        assert result["total_mw"] == pytest.approx(124.37, rel=0.01)

    def test_dynamic_leakage_split(self):
        result = pdr.parse_power(FIXTURES / "power.rpt")
        assert result["dynamic_mw"] == pytest.approx(98.21, rel=0.01)
        assert result["leakage_mw"] == pytest.approx(26.16, rel=0.01)

    def test_clock_power(self):
        result = pdr.parse_power(FIXTURES / "power.rpt")
        assert result["clock_mw"] == pytest.approx(42.10, rel=0.01)
        assert result["clock_pct"] == pytest.approx(33.87, rel=0.05)

    def test_internal_mw_alias_matches_register_mw(self):
        result = pdr.parse_power(FIXTURES / "power.rpt")
        assert result["internal_mw"] == result["register_mw"]

    def test_hierarchical_per_module(self):
        result = pdr.parse_power(FIXTURES / "power.rpt")
        assert len(result["per_module"]) >= 3, "must parse hierarchical entries"
        hiers = [m["hier"] for m in result["per_module"]]
        assert "top" not in hiers, "root 'top' row must be excluded from per_module"
        assert any("u_core" in h for h in hiers)
        u_core_entry = next(m for m in result["per_module"] if m["hier"] == "top/u_core")
        assert u_core_entry["pct"] == pytest.approx(57.27, rel=0.01)
        assert u_core_entry["total_mw"] == pytest.approx(71.22, rel=0.01)
        # The u_core row has an 'H' Attrs annotation — it must still be parsed
        u_core = next(m for m in result["per_module"] if m["hier"] == "top/u_core")
        assert u_core["total_mw"] == pytest.approx(71.22, rel=0.01)

    def test_hierarchical_per_module_with_non_top_name(self, tmp_path):
        content = textwrap.dedent("""
        Total Dynamic Power    =   98.21 mW
        Cell Leakage Power     =   26.16 mW
        Cell Internal Power    =   55.00 mW
        Total Power            =  124.37 mW

        Hierarchical Power Distribution:
          vc_transform_8x8     10.00  20.00  5.00  124.37  100.00
            vc_transform_8x8/u_core   5.00  10.00  2.50   71.22   57.27 H
            vc_transform_8x8/u_io     2.00   4.00  1.00   30.00   24.13
        """)
        rpt = tmp_path / "power.rpt"
        rpt.write_text(content)
        result = pdr.parse_power(rpt)
        hiers = [m["hier"] for m in result["per_module"]]
        # Non-top root must be excluded (depth 0)
        assert "vc_transform_8x8" not in hiers
        # Child modules must be captured
        assert "vc_transform_8x8/u_core" in hiers
        assert "vc_transform_8x8/u_io" in hiers


class TestParseQor:
    def test_wns_tns(self):
        result = pdr.parse_qor(FIXTURES / "qor.rpt")
        assert result["design_wns_ns"] == pytest.approx(-0.083)
        assert result["design_tns_ns"] == pytest.approx(-2.410)

    def test_status_violated(self):
        result = pdr.parse_qor(FIXTURES / "qor.rpt")
        assert result["status"] == "TIMING_VIOLATION"

    def test_num_violating_paths(self):
        result = pdr.parse_qor(FIXTURES / "qor.rpt")
        assert result["num_violating_paths"] == 17


class TestParseClockGating:
    def test_totals(self):
        result = pdr.parse_clock_gating(FIXTURES / "clock_gating.rpt")
        assert result["total_registers"] == 3421
        assert result["gated_registers"] == 2871
        assert result["gating_efficiency_pct"] == pytest.approx(83.9, rel=0.01)

    def test_ungated_banks(self):
        result = pdr.parse_clock_gating(FIXTURES / "clock_gating.rpt")
        hiers = [b["hier"] for b in result["ungated_banks"]]
        assert "top/u_io_ctrl/cfg_reg" in hiers


class TestParseVtGroup:
    def test_percentages(self):
        result = pdr.parse_vt_group(FIXTURES / "vt.rpt")
        assert result["LVT_pct"] == pytest.approx(4.2)
        assert result["SVT_pct"] == pytest.approx(61.8)
        assert result["HVT_pct"] == pytest.approx(34.0)


class TestIntegration:
    def test_main_writes_expected_json(self, tmp_path, monkeypatch):
        out_path = tmp_path / "ppa-report.json"
        monkeypatch.setenv("PPA_TOOL", "dc_shell")
        monkeypatch.setenv("PPA_TOP", "vc_transform_8x8")
        monkeypatch.setenv("PPA_ITER", "3")
        monkeypatch.setenv("PPA_LIBERTY", "/libs/tcbn07.lib")
        monkeypatch.setenv("PPA_SDC", "syn/constraints/design.sdc")
        pdr.run(str(FIXTURES), str(out_path))
        data = json.loads(out_path.read_text())
        assert data["schema_version"] == "1.1"
        assert data["tool"] == "dc_shell"
        assert data["design"] == "vc_transform_8x8"
        assert data["iteration"] == 3
        assert data["area"]["total_um2"] == pytest.approx(45230.5, rel=0.01)
        assert data["timing"]["wns_ns"] == pytest.approx(-0.083)
        assert data["power"]["total_mw"] == pytest.approx(124.37, rel=0.01)
        assert len(data["power"]["per_module"]) >= 3, "per_module must be non-empty"
        assert data["qor"]["status"] == "TIMING_VIOLATION"
        assert data["clock_gating"]["total_registers"] == 3421
        assert data["vt_group"]["LVT_pct"] == pytest.approx(4.2)
