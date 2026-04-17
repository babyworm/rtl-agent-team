# PPA Optimizer (DC-based) — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Design Compiler–centric PPA optimization loop as a post-verify stage with equivalence-verified RTL patching, timing-first heuristic, and early-plateau user escalation.

**Architecture:** Action Skill (`rtl-ppa-optimize-dc`) + auto-loop wrapper (`rat-ultraloop-ppa`) → Orchestrator agent → Specialist agents (patcher, report-parser, equivalence-checker) → Policy skill (heuristic, Tcl fragments, convergence rules). Per-iteration: DC synth → JSON consolidation → patch → equiv + smoke → Δ computation → convergence check.

**Tech Stack:** Python 3 (stdlib only), Bash (hook modifications), Markdown (skills/agents), JSON (state), Tcl (DC fragments). Commercial DC (`dc_shell`) or Genus required at runtime; all tests run on fixtures.

**Spec:** `plugin_docs/specs/2026-04-17-ppa-optimizer-dc-design.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py` | Consolidate DC `.rpt` files → `ppa-report.json` |
| Create | `skills/rtl-ppa-optimize-dc/scripts/compute_delta.py` | Weighted Δ + convergence verdict |
| Create | `skills/rtl-ppa-optimize-dc/scripts/validate_patch_scope.py` | Verify `patch.diff` touches only `allowed_edit_scope` |
| Create | `skills/rtl-ppa-optimize-dc/SKILL.md` | Action skill (one-shot iteration) |
| Create | `skills/rat-ultraloop-ppa/SKILL.md` | Auto-loop wrapper (convergence-driven) |
| Create | `skills/ppa-optimizer-dc-policy/SKILL.md` | Heuristic / weights / convergence / Tcl reference |
| Create | `skills/ppa-optimizer-dc-policy/templates/dc-compile-ppa.tcl` | Tcl fragment for DC compile |
| Create | `skills/ppa-optimizer-dc-policy/templates/ppa-brief-scaffold.json` | `requirements.json` `ppa_targets` scaffold |
| Create | `agents/ppa-optimizer-dc.md` | RTL patcher agent (timing-first) |
| Create | `agents/dc-report-parser.md` | Parser wrapper agent |
| Create | `agents/ppa-optimizer-dc-orchestrator.md` | Iteration coordinator |
| Create | `tests/fixtures/dc-reports/area.rpt` | Synthetic DC area report |
| Create | `tests/fixtures/dc-reports/timing.rpt` | Synthetic DC timing report |
| Create | `tests/fixtures/dc-reports/power.rpt` | Synthetic DC power report |
| Create | `tests/fixtures/dc-reports/qor.rpt` | Synthetic DC QoR report |
| Create | `tests/fixtures/dc-reports/clock_gating.rpt` | Synthetic clock gating report |
| Create | `tests/fixtures/dc-reports/vt.rpt` | Synthetic Vt group report |
| Create | `tests/fixtures/dc-reports/expected-ppa-report.json` | Expected parser output |
| Create | `tests/unit/test_parse_dc_reports.py` | Parser unit tests |
| Create | `tests/unit/test_compute_delta.py` | Delta/convergence unit tests |
| Create | `tests/unit/test_validate_patch_scope.py` | Scope guard unit tests |
| Modify | `hooks/rtl-edit-tracker.sh` | Skip staleness counting during PPA loop |
| Modify | `hooks/stop-gate.sh` | Recognize `mode: "ppa-loop"` for auto-continue |
| Modify | `hooks/rtl-p6-cascade-gate.sh` | Flag P6 re-review on `.rat/state/ppa-opt-done` |
| Modify | `skill-completion-criteria.json` | Register new skills |
| Modify | `phase-registry.json` | Add `ppa-opt` phase + skill/agent mappings |
| Modify | `skills/rtl-orchestrate/SKILL.md` | Add routing entries |
| Modify | `hooks/rtl-orchestrator-inject.sh` | Regenerated via sync script |
| Modify | `CLAUDE.md` | Add Rules 10/11 + update component counts |
| Modify | `package.json` | Version 0.9.3 → 0.10.0 |
| Modify | `.claude-plugin/plugin.json` | Version 0.9.3 → 0.10.0 |
| Modify | `.claude-plugin/marketplace.json` | Metadata + plugins[0] version bump |
| Modify | `README.md` | Skill/agent counts + marketplace table |
| Modify | `README_kr.md` | Same as above |
| Modify | `CHANGELOG.md` | New `[0.10.0] - 2026-04-17` section |

---

## Task 1: DC Report Fixtures

**Files:**
- Create: `tests/fixtures/dc-reports/area.rpt`
- Create: `tests/fixtures/dc-reports/timing.rpt`
- Create: `tests/fixtures/dc-reports/power.rpt`
- Create: `tests/fixtures/dc-reports/qor.rpt`
- Create: `tests/fixtures/dc-reports/clock_gating.rpt`
- Create: `tests/fixtures/dc-reports/vt.rpt`

- [ ] **Step 1.1: Create fixtures directory**

```bash
mkdir -p tests/fixtures/dc-reports
```

- [ ] **Step 1.2: Write area.rpt**

Write this exact content to `tests/fixtures/dc-reports/area.rpt`:

```
****************************************
Report : area
Design : vc_transform_8x8
Version: U-2023.12
Date   : Wed Apr 17 12:14:22 2026
****************************************

Library(s) Used:

    tcbn07bwp7t30p140ffg0p88v0c (File: /libs/tcbn07.lib)

Number of ports:                         412
Number of nets:                         4821
Number of cells:                        3102
Number of combinational cells:          1814
Number of sequential cells:             1245
Number of macros/black boxes:              0
Number of buf/inv:                       412
Number of references:                     42

Combinational area:              28150.200012
Buf/Inv area:                     2341.700001
Noncombinational area:           17080.300022
Macro/Black Box area:                0.000000
Net Interconnect area:             undefined  (Wire load has zero net area)

Total cell area:                 45230.500034
Total area:                        undefined

Hierarchical area distribution:
  top                                   45230.5  100.00%
    top/u_core                          12345.6   27.30%
    top/u_core/u_s1                      4821.2   10.66%
    top/u_core/u_s2                      4221.7    9.33%
    top/u_io_ctrl                        3200.4    7.07%
    top/u_ram_ctrl                       2100.0    4.64%
1
```

- [ ] **Step 1.3: Write timing.rpt**

Write this exact content to `tests/fixtures/dc-reports/timing.rpt`:

```
****************************************
Report : timing
        -path full
        -delay max
        -max_paths 10
        -sort_by group
Design : vc_transform_8x8
Version: U-2023.12
Date   : Wed Apr 17 12:14:45 2026
****************************************

Operating Conditions: ffg0p88v0c   Library: tcbn07bwp7t30p140ffg0p88v0c
Wire Load Model Mode: top

  Startpoint: u_core/u_s1/pix_reg[7] (rising edge-triggered flip-flop clocked by sys_clk)
  Endpoint: u_core/u_s2/sum_reg[15] (rising edge-triggered flip-flop clocked by sys_clk)
  Path Group: sys_clk
  Path Type: max

  Point                                    Incr       Path
  -----------------------------------------------------------
  clock sys_clk (rise edge)                0.00       0.00
  clock network delay (ideal)              0.00       0.00
  u_core/u_s1/pix_reg[7]/CP (DFCNQD4BWP)   0.00       0.00 r
  ...
  u_core/u_s2/sum_reg[15]/D (DFCNQD4BWP)   0.00       1.201
  data arrival time                                    1.201

  clock sys_clk (rise edge)                1.250      1.250
  clock network delay (ideal)              0.000      1.250
  u_core/u_s2/sum_reg[15]/CP (DFCNQD4BWP)              1.250 r
  library setup time                      -0.034      1.216
  data required time                                   1.216
  -----------------------------------------------------------
  data required time                                   1.216
  data arrival time                                   -1.201
  -----------------------------------------------------------
  slack (VIOLATED)                                    -0.083


  Startpoint: u_core/u_s2/mul_a_reg[11] (rising edge-triggered flip-flop clocked by sys_clk)
  Endpoint: u_core/u_s3/acc_reg[27] (rising edge-triggered flip-flop clocked by sys_clk)
  Path Group: sys_clk
  Path Type: max

  data arrival time                                    1.150
  data required time                                   1.216
  slack (MET)                                          0.066

Clock sys_clk (rise edge) at period 1.25 ns

1
```

- [ ] **Step 1.4: Write power.rpt**

Write this exact content to `tests/fixtures/dc-reports/power.rpt`:

```
****************************************
Report : power
        -analysis_effort high
Design : vc_transform_8x8
Version: U-2023.12
Date   : Wed Apr 17 12:15:12 2026
****************************************

Library(s) Used:

    tcbn07bwp7t30p140ffg0p88v0c (File: /libs/tcbn07.lib)

Operating Conditions: ffg0p88v0c   Library: tcbn07bwp7t30p140ffg0p88v0c
Wire Load Model Mode: top

Global Operating Voltage = 0.88
Power-specific unit information :
    Voltage Units = 1V
    Capacitance Units = 1.000000pf
    Time Units = 1ns
    Dynamic Power Units = 1mW    (derived from V,C,T units)
    Leakage Power Units = 1nW

  Cell Internal Power  =  14.92 mW   (12%)
  Net Switching Power  =  83.29 mW   (67%)
                         ---------
Total Dynamic Power    =  98.21 mW   (79%)

Cell Leakage Power     =  26.16 mW

                 Internal     Switching     Leakage      Total
Power Group      Power        Power         Power        Power    (  %)  Attrs
---------------------------------------------------------------------------
clock_network      14.1          28.0          0.0        42.10   (33.87%)
register            2.2           4.7          8.0        14.92   (12.00%)
combinational       1.1           1.2          0.5         2.75   ( 2.21%)
black_box           0.0           0.0          0.0         0.00   ( 0.00%)
---------------------------------------------------------------------------
Total           17.4 mW       38.44 mW      26.16 mW    124.37 mW

Total Power = 124.37 mW

1
```

- [ ] **Step 1.5: Write qor.rpt**

Write this exact content to `tests/fixtures/dc-reports/qor.rpt`:

```
****************************************
Report : qor
Design : vc_transform_8x8
Version: U-2023.12
Date   : Wed Apr 17 12:15:34 2026
****************************************


  Timing Path Group 'sys_clk'
  -----------------------------------
  Levels of Logic:             17.00
  Critical Path Length:         1.20
  Critical Path Slack:         -0.083
  Critical Path Clk Period:     1.25
  Total Negative Slack:        -2.410
  No. of Violating Paths:      17.00
  Worst Hold Violation:         0.000
  Total Hold Violation:         0.000
  No. of Hold Violations:        0.00
  -----------------------------------


  Design WNS:  -0.083
  Design TNS:  -2.410
  Worst Hold Slack:  0.023


  DESIGN STATISTICS
  -----------------------------------
  Area Summary (based on 0.798 um2 per NAND2X1):
    Total Cell Area:   45230.500
  Cell Count:
    Hierarchical Cell Count:    3102
    Hierarchical Port Count:     412
    Leaf Cell Count:            3102
1
```

- [ ] **Step 1.6: Write clock_gating.rpt**

Write this exact content to `tests/fixtures/dc-reports/clock_gating.rpt`:

```
****************************************
Report : clock_gating -verbose
Design : vc_transform_8x8
Version: U-2023.12
Date   : Wed Apr 17 12:15:58 2026
****************************************

Clock gating summary:
--------------------------------------------------
|           |     Total |   Gated |   Ungated |
|           | registers | regs    | regs      |
--------------------------------------------------
| Design    |      3421 |    2871 |       550 |
--------------------------------------------------

Total registers:  3421
Gated registers:  2871
Ungated registers: 550
Gating efficiency: 83.92%

Ungated bank details:
    top/u_io_ctrl/cfg_reg     Ungated       32
    top/u_ram_ctrl/addr_reg   Ungated        8
    top/u_core/u_s1/stat_reg  Ungated       16
1
```

- [ ] **Step 1.7: Write vt.rpt**

Write this exact content to `tests/fixtures/dc-reports/vt.rpt`:

```
****************************************
Report : threshold_voltage_group
Design : vc_transform_8x8
Version: U-2023.12
Date   : Wed Apr 17 12:16:22 2026
****************************************

Threshold Voltage Group Usage:
----------------------------------------
| Vt Group | Cell Count |  Area  |   %  |
----------------------------------------
| LVT      |        131 | 1899.7 |  4.2 |
| SVT      |       1919 | 27952.5|  61.8|
| HVT      |       1052 | 15378.3|  34.0|
----------------------------------------
Total cell area: 45230.5 um2
LVT: 4.2 %
SVT: 61.8 %
HVT: 34.0 %
1
```

- [ ] **Step 1.8: Commit fixtures**

```bash
git add tests/fixtures/dc-reports/
git commit -m "test(ppa): add DC report fixtures for parser tests"
```

---

## Task 2: parse_dc_reports.py — Core Parser

**Files:**
- Create: `skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py`
- Create: `tests/unit/test_parse_dc_reports.py`

- [ ] **Step 2.1: Create scripts directory**

```bash
mkdir -p skills/rtl-ppa-optimize-dc/scripts
```

- [ ] **Step 2.2: Write test file skeleton**

Write this content to `tests/unit/test_parse_dc_reports.py`:

```python
"""Unit tests for parse_dc_reports.py — DC .rpt → ppa-report.json."""
import json
import os
import pathlib
import sys

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
        u_core = next(m for m in result["per_module"] if m["hier"] == "top/u_core")
        assert u_core["um2"] == pytest.approx(12345.6)
        assert u_core["pct"] == pytest.approx(27.30, rel=0.01)

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


class TestParseQor:
    def test_wns_tns(self):
        result = pdr.parse_qor(FIXTURES / "qor.rpt")
        assert result["design_wns_ns"] == pytest.approx(-0.083)
        assert result["design_tns_ns"] == pytest.approx(-2.410)

    def test_status_violated(self):
        result = pdr.parse_qor(FIXTURES / "qor.rpt")
        assert result["status"] == "TIMING_VIOLATION"


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
        assert data["schema_version"] == "1.0"
        assert data["tool"] == "dc_shell"
        assert data["design"] == "vc_transform_8x8"
        assert data["iteration"] == 3
        assert data["area"]["total_um2"] == pytest.approx(45230.5, rel=0.01)
        assert data["timing"]["wns_ns"] == pytest.approx(-0.083)
        assert data["power"]["total_mw"] == pytest.approx(124.37, rel=0.01)
        assert data["qor"]["status"] == "TIMING_VIOLATION"
        assert data["clock_gating"]["total_registers"] == 3421
        assert data["vt_group"]["LVT_pct"] == pytest.approx(4.2)
```

- [ ] **Step 2.3: Run tests to confirm failure**

```bash
python3 -m pytest tests/unit/test_parse_dc_reports.py -x -q
```
Expected: all tests FAIL with `ModuleNotFoundError: No module named 'parse_dc_reports'`.

- [ ] **Step 2.4: Write parse_dc_reports.py**

Write this content to `skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py`:

```python
#!/usr/bin/env python3
"""Parse Synopsys Design Compiler .rpt files into a unified ppa-report.json.

Invocation:
    parse_dc_reports.py <syn/rpt/ directory> [<output.json>]

Environment (all optional, used to annotate the JSON):
    PPA_TOOL     — "dc_shell" (default) or "genus"
    PPA_TOP      — top-level design name
    PPA_ITER     — iteration index (integer)
    PPA_LIBERTY  — path to liberty file
    PPA_SDC      — path to SDC constraints file

The parser uses the Python stdlib only (no external dependencies).
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys


REPORT_FILES = {
    "area":         ["area.rpt", "*_area.rpt"],
    "timing":       ["timing.rpt", "*_timing.rpt"],
    "power":        ["power.rpt", "*_power.rpt"],
    "qor":          ["qor.rpt", "*_qor.rpt"],
    "clock_gating": ["clock_gating.rpt", "*_clock_gating.rpt"],
    "vt_group":     ["vt.rpt", "*_vt*.rpt", "*threshold_voltage*.rpt"],
}


def find_file(rpt_dir, patterns):
    p = pathlib.Path(rpt_dir)
    for pattern in patterns:
        if not any(c in pattern for c in "*?"):
            candidate = p / pattern
            if candidate.exists():
                return candidate
        else:
            for match in p.glob(pattern):
                return match
    return None


def _to_mw(value, unit):
    unit = unit.lower()
    if unit == "w":
        return value * 1000.0
    if unit == "mw":
        return value
    if unit == "uw":
        return value * 1e-3
    if unit == "nw":
        return value * 1e-6
    return value


def parse_area(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {
        "total_um2": 0.0,
        "combinational_um2": 0.0,
        "sequential_um2": 0.0,
        "buf_inv_um2": 0.0,
        "macro_um2": 0.0,
        "per_module": [],
    }
    patterns = [
        ("total_um2",          r"Total cell area:\s*([\d.]+)"),
        ("combinational_um2",  r"Combinational area:\s*([\d.]+)"),
        ("sequential_um2",     r"Noncombinational area:\s*([\d.]+)"),
        ("buf_inv_um2",        r"Buf/Inv area:\s*([\d.]+)"),
        ("macro_um2",          r"Macro/Black Box area:\s*([\d.]+)"),
    ]
    for key, pat in patterns:
        m = re.search(pat, text)
        if m:
            result[key] = float(m.group(1))
    hier_re = re.compile(
        r"^\s+(top(?:/[\w\[\]\.]+)*)\s+([\d.]+)\s+([\d.]+)%",
        re.MULTILINE,
    )
    for m in hier_re.finditer(text):
        hier, um2, pct = m.groups()
        result["per_module"].append(
            {"hier": hier, "um2": float(um2), "pct": float(pct), "cells": 0}
        )
    return result


def parse_timing(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {
        "clock": "",
        "period_ns": 0.0,
        "wns_ns": 0.0,
        "tns_ns": 0.0,
        "num_violating_paths": 0,
        "critical_paths": [],
    }
    m = re.search(r"Clock\s+(\S+)\s+\(rise edge\)\s+at period\s+([\d.]+)", text)
    if m:
        result["clock"] = m.group(1)
        result["period_ns"] = float(m.group(2))
    else:
        m = re.search(r"clock\s+(\S+)\s+\(rise edge\)", text)
        if m:
            result["clock"] = m.group(1)
        m = re.search(r"Path Group:\s+(\S+).*?period\s+([\d.]+)", text, re.DOTALL)
        if m:
            result["period_ns"] = float(m.group(2))
    worst_slack = None
    for m in re.finditer(r"slack\s+\((?:VIOLATED|MET)\)\s+(-?[\d.]+)", text):
        slack = float(m.group(1))
        if worst_slack is None or slack < worst_slack:
            worst_slack = slack
    if worst_slack is not None:
        result["wns_ns"] = worst_slack
    path_re = re.compile(
        r"Startpoint:\s*(\S+).*?"
        r"Endpoint:\s*(\S+).*?"
        r"data arrival time\s+(-?[\d.]+).*?"
        r"slack\s+\((VIOLATED|MET)\)\s+(-?[\d.]+)",
        re.DOTALL,
    )
    for rank, m in enumerate(list(path_re.finditer(text))[:10], 1):
        start, end, arrival, _status, slack = m.groups()
        result["critical_paths"].append(
            {
                "rank": rank,
                "from": start,
                "to": end,
                "slack_ns": float(slack),
                "data_delay_ns": float(arrival),
                "logic_levels": 0,
                "top_cells": [],
            }
        )
    return result


def parse_power(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {
        "analysis_effort": "high",
        "total_mw": 0.0,
        "dynamic_mw": 0.0,
        "leakage_mw": 0.0,
        "clock_mw": 0.0,
        "clock_pct": 0.0,
        "net_mw": 0.0,
        "register_mw": 0.0,
        "combinational_mw": 0.0,
        "macro_mw": 0.0,
        "per_module": [],
    }
    labels = [
        ("Total Dynamic Power", "dynamic_mw"),
        ("Cell Leakage Power",  "leakage_mw"),
        ("Net Switching Power", "net_mw"),
        ("Cell Internal Power", "register_mw"),
        ("Total Power",         "total_mw"),
    ]
    for label, key in labels:
        m = re.search(
            rf"{re.escape(label)}\s*=\s*([\d.eE+-]+)\s*(\w+)",
            text,
        )
        if m:
            result[key] = _to_mw(float(m.group(1)), m.group(2))
    group_re = re.compile(
        r"^(clock_network|register|combinational|black_box)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\(\s*([\d.]+)%\)",
        re.MULTILINE,
    )
    for m in group_re.finditer(text):
        group, _internal, _switching, _leakage, total, pct = m.groups()
        if group == "clock_network":
            result["clock_mw"] = float(total)
            result["clock_pct"] = float(pct)
        elif group == "combinational":
            result["combinational_mw"] = float(total)
    return result


def parse_qor(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {
        "design_wns_ns": 0.0,
        "design_tns_ns": 0.0,
        "worst_hold_slack_ns": 0.0,
        "status": "PASS",
    }
    m = re.search(r"Design WNS:\s+(-?[\d.]+)", text)
    if m:
        result["design_wns_ns"] = float(m.group(1))
    m = re.search(r"Design TNS:\s+(-?[\d.]+)", text)
    if m:
        result["design_tns_ns"] = float(m.group(1))
    m = re.search(r"Worst Hold Slack:\s+(-?[\d.]+)", text)
    if m:
        result["worst_hold_slack_ns"] = float(m.group(1))
    if result["design_wns_ns"] < 0:
        result["status"] = "TIMING_VIOLATION"
    return result


def parse_clock_gating(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {
        "total_registers": 0,
        "gated_registers": 0,
        "gating_efficiency_pct": 0.0,
        "ungated_banks": [],
    }
    m = re.search(r"Total registers:\s+(\d+)", text)
    if m:
        result["total_registers"] = int(m.group(1))
    m = re.search(r"Gated registers:\s+(\d+)", text)
    if m:
        result["gated_registers"] = int(m.group(1))
    if result["total_registers"] > 0:
        result["gating_efficiency_pct"] = (
            100.0 * result["gated_registers"] / result["total_registers"]
        )
    for m in re.finditer(
        r"^\s+(\S+)\s+Ungated\s+(\d+)", text, re.MULTILINE
    ):
        result["ungated_banks"].append(
            {"hier": m.group(1), "registers": int(m.group(2))}
        )
    return result


def parse_vt_group(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {"LVT_pct": 0.0, "SVT_pct": 0.0, "HVT_pct": 0.0}
    for label, key in [
        ("LVT", "LVT_pct"),
        ("SVT", "SVT_pct"),
        ("HVT", "HVT_pct"),
    ]:
        m = re.search(rf"^{label}:\s*([\d.]+)\s*%", text, re.MULTILINE)
        if m:
            result[key] = float(m.group(1))
    return result


def parse_warnings(rpt_dir):
    warnings = []
    p = pathlib.Path(rpt_dir)
    for rpt in p.glob("*.rpt"):
        text = rpt.read_text()
        for m in re.finditer(
            r"latch\s+inferred.*?(\S+\.sv:\d+)", text, re.IGNORECASE
        ):
            warnings.append(
                {"category": "inferred_latch", "detail": m.group(1)}
            )
        for m in re.finditer(r"GTECH_\w+", text):
            warnings.append(
                {"category": "unmapped_cell", "detail": m.group(0)}
            )
    return warnings


def run(rpt_dir, out_path):
    report = {
        "schema_version": "1.0",
        "tool": os.environ.get("PPA_TOOL", "dc_shell"),
        "design": os.environ.get("PPA_TOP", "unknown"),
        "iteration": int(os.environ.get("PPA_ITER", "0")),
        "timestamp": datetime.datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "liberty": os.environ.get("PPA_LIBERTY", ""),
        "sdc": os.environ.get("PPA_SDC", "syn/constraints/design.sdc"),
    }
    files = {
        kind: find_file(rpt_dir, patterns)
        for kind, patterns in REPORT_FILES.items()
    }
    report["area"] = parse_area(files["area"])
    report["timing"] = parse_timing(files["timing"])
    report["power"] = parse_power(files["power"])
    report["qor"] = parse_qor(files["qor"])
    report["clock_gating"] = parse_clock_gating(files["clock_gating"])
    report["vt_group"] = parse_vt_group(files["vt_group"])
    report["warnings"] = parse_warnings(rpt_dir)

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    return report


def main(argv):
    if len(argv) < 2:
        print(
            "Usage: parse_dc_reports.py <syn/rpt/ directory> [<output.json>]",
            file=sys.stderr,
        )
        return 1
    rpt_dir = argv[1]
    out_path = argv[2] if len(argv) > 2 else "syn/ppa-report.json"
    run(rpt_dir, out_path)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 2.5: Run tests to verify pass**

```bash
python3 -m pytest tests/unit/test_parse_dc_reports.py -x -q
```
Expected: all tests PASS.

- [ ] **Step 2.6: Commit**

```bash
git add skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py \
        tests/unit/test_parse_dc_reports.py
git commit -m "feat(ppa): add DC report parser with JSON output"
```

---

## Task 3: compute_delta.py — Convergence Logic

**Files:**
- Create: `skills/rtl-ppa-optimize-dc/scripts/compute_delta.py`
- Create: `tests/unit/test_compute_delta.py`

- [ ] **Step 3.1: Write test file**

Write this content to `tests/unit/test_compute_delta.py`:

```python
"""Unit tests for compute_delta.py — weighted Δ + convergence verdict."""
import json
import pathlib
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "skills" / "rtl-ppa-optimize-dc" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import compute_delta as cd  # noqa: E402


def _report(wns, power_mw, area_um2):
    return {
        "timing": {"wns_ns": wns},
        "power": {"total_mw": power_mw},
        "area": {"total_um2": area_um2},
    }


def _state(cycle, max_cycles=4, history=None, streak_req=3, delta_pct=2.0, early_pct=1.0):
    return {
        "mode": "ppa-loop",
        "cycle": cycle,
        "max_cycles": max_cycles,
        "convergence": {
            "delta_pct": delta_pct,
            "streak_required": streak_req,
            "early_plateau_pct": early_pct,
            "history": history or [],
        },
    }


def _targets(period=1.25, power=100.0, area=50000.0):
    return {
        "timing_slack_ns": 0.10,
        "power_mw": power,
        "area_um2": area,
        "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
    }


class TestNormalizeWeights:
    def test_unit_sum(self):
        w = cd.normalize_weights({"timing": 0.7, "power": 0.2, "area": 0.1})
        assert pytest.approx(sum(w.values())) == 1.0

    def test_non_unit_sum(self):
        w = cd.normalize_weights({"timing": 7, "power": 2, "area": 1})
        assert w["timing"] == pytest.approx(0.7)
        assert w["power"] == pytest.approx(0.2)
        assert w["area"] == pytest.approx(0.1)

    def test_zero_sum_raises(self):
        with pytest.raises(ValueError):
            cd.normalize_weights({"timing": 0, "power": 0, "area": 0})


class TestWeightedDelta:
    def test_improvement_is_positive(self):
        prev = _report(-0.12, 135.0, 48000.0)
        curr = _report(-0.08, 127.0, 46000.0)
        delta = cd.weighted_delta(curr, prev, _targets(), _targets()["weights"])
        assert delta > 0

    def test_regression_is_negative(self):
        prev = _report(-0.08, 127.0, 46000.0)
        curr = _report(-0.12, 135.0, 48000.0)
        delta = cd.weighted_delta(curr, prev, _targets(), _targets()["weights"])
        assert delta < 0


class TestEvaluateConvergence:
    def test_first_iter_no_delta(self):
        state = _state(cycle=1)
        curr = _report(-0.12, 135.0, 48000.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "CONTINUE"
        assert state["convergence"]["history"][-1]["weighted_delta_pct"] is None

    def test_streak_convergence(self):
        history = [
            {"iter": 1, "wns_ns": -0.12, "power_mw": 135.0, "area_um2": 48000.0, "weighted_delta_pct": None},
            {"iter": 2, "wns_ns": -0.10, "power_mw": 132.0, "area_um2": 47500.0, "weighted_delta_pct": 1.2},
            {"iter": 3, "wns_ns": -0.095, "power_mw": 130.0, "area_um2": 47200.0, "weighted_delta_pct": 1.0},
        ]
        state = _state(cycle=4, history=history)
        curr = _report(-0.094, 129.5, 47100.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "CONVERGED_STREAK"

    def test_all_targets_met(self):
        state = _state(cycle=2)
        curr = _report(0.05, 80.0, 44000.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "CONVERGED_TARGETS"

    def test_early_plateau(self):
        history = [
            {"iter": 1, "wns_ns": -0.12, "power_mw": 135.0, "area_um2": 48000.0, "weighted_delta_pct": None},
        ]
        state = _state(cycle=2, history=history)
        curr = _report(-0.1195, 134.8, 47990.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "EARLY_PLATEAU"

    def test_max_cycles(self):
        history = [
            {"iter": i, "wns_ns": -0.1, "power_mw": 130.0, "area_um2": 47000.0, "weighted_delta_pct": 3.0}
            for i in range(1, 4)
        ]
        state = _state(cycle=4, max_cycles=4, history=history)
        curr = _report(-0.08, 125.0, 46500.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "MAX_CYCLES"
```

- [ ] **Step 3.2: Run tests to confirm failure**

```bash
python3 -m pytest tests/unit/test_compute_delta.py -x -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'compute_delta'`.

- [ ] **Step 3.3: Write compute_delta.py**

Write this content to `skills/rtl-ppa-optimize-dc/scripts/compute_delta.py`:

```python
#!/usr/bin/env python3
"""Compute weighted PPA delta and evaluate convergence / early-plateau.

Reads:
    - Current ppa-report.json
    - .rat/state/ppa-loop-state.json (mutated in-place)
    - requirements.json["ppa_targets"]

Writes updated state file in place and prints verdict:
    CONTINUE | CONVERGED_STREAK | CONVERGED_TARGETS | EARLY_PLATEAU | MAX_CYCLES
"""
from __future__ import annotations

import json
import pathlib
import sys


VALID_VERDICTS = {
    "CONTINUE",
    "CONVERGED_STREAK",
    "CONVERGED_TARGETS",
    "EARLY_PLATEAU",
    "MAX_CYCLES",
}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def normalize_weights(w):
    s = sum(w.values())
    if s <= 0:
        raise ValueError("weights sum must be positive")
    return {k: v / s for k, v in w.items()}


def weighted_delta(curr, prev, targets, weights):
    target_period = float(targets.get("timing_slack_ns", 0.10)) + 0.01
    target_power = float(targets.get("power_mw", 100.0))
    target_area = float(targets.get("area_um2", 50000.0))
    d_timing = (curr["timing"]["wns_ns"] - prev["timing"]["wns_ns"]) / target_period
    d_power = (prev["power"]["total_mw"] - curr["power"]["total_mw"]) / target_power
    d_area = (prev["area"]["total_um2"] - curr["area"]["total_um2"]) / target_area
    w = normalize_weights(weights)
    return 100.0 * (w["timing"] * d_timing + w["power"] * d_power + w["area"] * d_area)


def targets_met(report, targets):
    return {
        "timing": report["timing"]["wns_ns"] >= -0.001,
        "power": report["power"]["total_mw"] <= float(targets.get("power_mw", 1e9)),
        "area": report["area"]["total_um2"] <= float(targets.get("area_um2", 1e9)),
    }


def evaluate_convergence(state, curr_report, targets, weights):
    conv = state.setdefault("convergence", {})
    history = conv.setdefault("history", [])
    iter_n = int(state.get("cycle", len(history) + 1))

    entry = {
        "iter": iter_n,
        "wns_ns": curr_report["timing"]["wns_ns"],
        "power_mw": curr_report["power"]["total_mw"],
        "area_um2": curr_report["area"]["total_um2"],
        "weighted_delta_pct": None,
    }
    if history:
        prev_entry = history[-1]
        prev_report = {
            "timing": {"wns_ns": prev_entry["wns_ns"]},
            "power": {"total_mw": prev_entry["power_mw"]},
            "area": {"total_um2": prev_entry["area_um2"]},
        }
        entry["weighted_delta_pct"] = weighted_delta(
            curr_report, prev_report, targets, weights
        )
    history.append(entry)

    conv["targets_met"] = targets_met(curr_report, targets)

    delta_pct = float(conv.get("delta_pct", 2.0))
    streak_req = int(conv.get("streak_required", 3))
    early_pct = float(conv.get("early_plateau_pct", 1.0))
    max_cycles = int(state.get("max_cycles", 4))

    with_delta = [h for h in history if h["weighted_delta_pct"] is not None]
    current_streak = 0
    for h in reversed(with_delta):
        if abs(h["weighted_delta_pct"]) < delta_pct:
            current_streak += 1
        else:
            break
    conv["current_streak"] = current_streak

    if all(conv["targets_met"].values()):
        return "CONVERGED_TARGETS"
    if current_streak >= streak_req:
        return "CONVERGED_STREAK"
    if iter_n <= 2 and with_delta and all(
        abs(h["weighted_delta_pct"]) < early_pct
        for h in with_delta[-min(2, len(with_delta)) :]
    ):
        return "EARLY_PLATEAU"
    if iter_n >= max_cycles:
        return "MAX_CYCLES"
    return "CONTINUE"


def main(argv):
    if len(argv) < 4:
        print(
            "Usage: compute_delta.py <curr.json> <state.json> <requirements.json>",
            file=sys.stderr,
        )
        return 1
    curr = load_json(argv[1])
    state = load_json(argv[2])
    req = load_json(argv[3])
    targets = req.get("ppa_targets", {})
    weights = targets.get("weights", {"timing": 0.7, "power": 0.2, "area": 0.1})
    verdict = evaluate_convergence(state, curr, targets, weights)
    if verdict not in VALID_VERDICTS:
        print(f"Internal error: invalid verdict '{verdict}'", file=sys.stderr)
        return 2
    pathlib.Path(argv[2]).write_text(json.dumps(state, indent=2))
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 3.4: Run tests to verify pass**

```bash
python3 -m pytest tests/unit/test_compute_delta.py -x -q
```
Expected: all tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add skills/rtl-ppa-optimize-dc/scripts/compute_delta.py \
        tests/unit/test_compute_delta.py
git commit -m "feat(ppa): add weighted delta + convergence verdict logic"
```

---

## Task 4: validate_patch_scope.py — Scope Guard

**Files:**
- Create: `skills/rtl-ppa-optimize-dc/scripts/validate_patch_scope.py`
- Create: `tests/unit/test_validate_patch_scope.py`

- [ ] **Step 4.1: Write test file**

Write this content to `tests/unit/test_validate_patch_scope.py`:

```python
"""Unit tests for validate_patch_scope.py — ensure patch stays within allowed scope."""
import pathlib
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "skills" / "rtl-ppa-optimize-dc" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_patch_scope as vps  # noqa: E402


def _diff(paths):
    """Build a synthetic unified diff touching each path."""
    hunks = []
    for p in paths:
        hunks.append(
            f"diff --git a/{p} b/{p}\n"
            f"--- a/{p}\n"
            f"+++ b/{p}\n"
            f"@@ -1,2 +1,2 @@\n"
            f"-old line\n"
            f"+new line\n"
        )
    return "".join(hunks)


class TestExtractChangedFiles:
    def test_single_file(self):
        diff = _diff(["rtl/core/datapath.sv"])
        files = vps.extract_changed_files(diff)
        assert files == ["rtl/core/datapath.sv"]

    def test_multiple_files(self):
        diff = _diff(["rtl/core/a.sv", "rtl/core/b.sv"])
        files = vps.extract_changed_files(diff)
        assert set(files) == {"rtl/core/a.sv", "rtl/core/b.sv"}

    def test_empty_diff(self):
        assert vps.extract_changed_files("") == []


class TestCheckScope:
    def test_allowed_file_passes(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**", "rtl/pkg/**"]
        ok, violations = vps.check_scope(["rtl/core/datapath.sv"], allowed, frozen)
        assert ok
        assert violations == []

    def test_frozen_violation(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**", "rtl/pkg/**"]
        ok, violations = vps.check_scope(
            ["rtl/common/sram_sp.sv", "rtl/core/datapath.sv"], allowed, frozen
        )
        assert not ok
        assert "rtl/common/sram_sp.sv" in violations

    def test_outside_allowed(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**"]
        ok, violations = vps.check_scope(
            ["rtl/unrelated/foo.sv"], allowed, frozen
        )
        assert not ok
        assert "rtl/unrelated/foo.sv" in violations

    def test_non_sv_file_outside_allowed(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**"]
        ok, violations = vps.check_scope(
            ["docs/notes.md"], allowed, frozen
        )
        assert not ok
```

- [ ] **Step 4.2: Run tests to confirm failure**

```bash
python3 -m pytest tests/unit/test_validate_patch_scope.py -x -q
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4.3: Write validate_patch_scope.py**

Write this content to `skills/rtl-ppa-optimize-dc/scripts/validate_patch_scope.py`:

```python
#!/usr/bin/env python3
"""Validate that a unified diff only touches allowed scope, never frozen scope.

Invocation:
    validate_patch_scope.py <patch.diff> <allowed_globs_csv> <frozen_globs_csv>

Exit 0 when patch is within scope; non-zero on violation (paths printed to stderr).
"""
from __future__ import annotations

import fnmatch
import pathlib
import re
import sys


DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/\S+", re.MULTILINE)


def extract_changed_files(diff_text):
    return DIFF_FILE_RE.findall(diff_text)


def _match(path, glob_list):
    for g in glob_list:
        if fnmatch.fnmatchcase(path, g):
            return True
        # support ** prefix style by substituting to * walks
        if "**" in g:
            simple = g.replace("**", "*")
            if fnmatch.fnmatchcase(path, simple):
                return True
    return False


def check_scope(files, allowed, frozen):
    violations = []
    for f in files:
        if _match(f, frozen):
            violations.append(f)
            continue
        if not _match(f, allowed):
            violations.append(f)
    return (not violations, violations)


def main(argv):
    if len(argv) < 4:
        print(
            "Usage: validate_patch_scope.py <patch.diff> <allowed_csv> <frozen_csv>",
            file=sys.stderr,
        )
        return 2
    diff_text = pathlib.Path(argv[1]).read_text()
    allowed = [s for s in argv[2].split(",") if s]
    frozen = [s for s in argv[3].split(",") if s]
    files = extract_changed_files(diff_text)
    ok, violations = check_scope(files, allowed, frozen)
    if not ok:
        for v in violations:
            print(f"SCOPE_VIOLATION: {v}", file=sys.stderr)
        return 1
    for f in files:
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4.4: Run tests to verify pass**

```bash
python3 -m pytest tests/unit/test_validate_patch_scope.py -x -q
```
Expected: PASS.

- [ ] **Step 4.5: Commit**

```bash
git add skills/rtl-ppa-optimize-dc/scripts/validate_patch_scope.py \
        tests/unit/test_validate_patch_scope.py
git commit -m "feat(ppa): add patch scope guard with allowed/frozen globs"
```

---

## Task 5: Policy Skill — ppa-optimizer-dc-policy

**Files:**
- Create: `skills/ppa-optimizer-dc-policy/SKILL.md`
- Create: `skills/ppa-optimizer-dc-policy/templates/dc-compile-ppa.tcl`
- Create: `skills/ppa-optimizer-dc-policy/templates/ppa-brief-scaffold.json`

- [ ] **Step 5.1: Create skill directory**

```bash
mkdir -p skills/ppa-optimizer-dc-policy/templates
```

- [ ] **Step 5.2: Write dc-compile-ppa.tcl**

Write this content to `skills/ppa-optimizer-dc-policy/templates/dc-compile-ppa.tcl`:

```tcl
# dc-compile-ppa.tcl — Design Compiler PPA-oriented compile fragment
# Applied by run_syn.sh --tool dc_shell when PPA-Opt loop is active.
# Intent: timing-first optimization with aggressive clock gating + leakage minimization.

# Clock gating strategy — latch-based ICG with fanout cap
set_clock_gating_style \
    -sequential_cell latch \
    -minimum_bitwidth 3 \
    -max_fanout 32 \
    -positive_edge_logic {integrated} \
    -control_point before \
    -control_signal scan_enable

# Compile strategy — ultra with retiming + scan-aware + clock gate insertion
compile_ultra \
    -timing \
    -gate_clock \
    -scan \
    -retime \
    -no_seq_output_inversion

# Leakage power optimization (post-compile incremental)
set_power_opt -leakage

# Additional reports to enable PPA analysis
report_clock_gating -verbose > syn/rpt/clock_gating.rpt
report_power -analysis_effort high > syn/rpt/power.rpt
report_threshold_voltage_group > syn/rpt/vt.rpt
report_timing -max_paths 10 -delay_type max > syn/rpt/timing.rpt
report_area -hier > syn/rpt/area.rpt
report_qor > syn/rpt/qor.rpt
```

- [ ] **Step 5.3: Write ppa-brief-scaffold.json**

Write this content to `skills/ppa-optimizer-dc-policy/templates/ppa-brief-scaffold.json`:

```json
{
  "ppa_targets": {
    "power_mw": 100.0,
    "timing_slack_ns": 0.10,
    "area_um2": 50000.0,
    "weights": {
      "timing": 0.7,
      "power": 0.2,
      "area": 0.1
    },
    "max_fanout": 32,
    "max_transition_ns": 0.30,
    "convergence": {
      "delta_pct": 2.0,
      "streak": 3,
      "early_plateau_pct": 1.0,
      "max_cycles": 4
    }
  }
}
```

- [ ] **Step 5.4: Write SKILL.md**

Write this content to `skills/ppa-optimizer-dc-policy/SKILL.md`:

```markdown
---
name: ppa-optimizer-dc-policy
description: "Policy rules, weights defaults, timing-first heuristic, convergence criteria, DC Tcl fragments, and rollback protocol for the DC-based PPA optimization pipeline. Pure reference — no orchestration."
user-invocable: false
---

# PPA Optimizer (DC-based) — Policy Reference

This is a **policy skill**: it defines rules and reference material consumed by
the `ppa-optimizer-dc` agent and the `ppa-optimizer-dc-orchestrator`. It is not
user-invocable.

## Optimization Philosophy

**Timing-first.** EDA tools (DC `compile_ultra -retime -gate_clock`) already
perform exhaustive optimization search; LLM RTL patches add value only where
tools cannot reach: missed clock gating opportunities, ill-shaped critical
paths solvable via pipelining, operand isolation on idle arithmetic blocks.
**Escalate to the user early when improvement stalls.**

## Default Weights

```
timing = 0.7
power  = 0.2
area   = 0.1
```

Loaded from `requirements.json["ppa_targets"]["weights"]`. Sum is normalized to
1.0 at runtime; a sum <= 0 is treated as a hard configuration error.

## Default Convergence Thresholds

```
delta_pct          = 2.0    # normal convergence Δ band
streak_required    = 3      # consecutive iterations with |Δ|<delta_pct
early_plateau_pct  = 1.0    # early-plateau Δ band (iter 1-2)
max_cycles         = 4      # hard stop unless user overrides
```

All overridable via `requirements.json["ppa_targets"]["convergence"]`.

## Three-Tier Termination

| Tier | Condition | Action |
|------|-----------|--------|
| Early plateau | At iter 1 or 2, every observed `|Δ_weighted|` < `early_plateau_pct` | Halt, emit `reviews/ppa-opt/early-plateau-escalation.md`, report to user |
| Normal convergence | Streak of `streak_required` iterations with `|Δ_weighted|` < `delta_pct` OR all targets met | Run full Phase 5 regression, emit `.rat/state/ppa-opt-done` |
| Max cycles | `iter == max_cycles` | Record best-so-far, escalate to user |

## Timing-First Heuristic (rule priority)

```
Rule 1 (HIGHEST · aggressive):  Timing closure
    - WNS < 0 → critical-path pipelining, retiming, logic restructuring
    - Logic levels > 12 @ 100 MHz → register rebalancing
    - REJECT any patch worsening WNS by more than 20 ps

Rule 2 (MAIN · safe):  Clock gating coverage
    - Identify ungated register banks (always_ff without enable)
    - Add enable conditions DC could not auto-infer
    - Goal: gating_efficiency_pct  80% → 90%+

Rule 3 (SECONDARY · timing-neutral):  Operand isolation
    - Target: multiplier / divider with idle cycles > 50%
    - Accepted only when timing slack unchanged

Rule 4 (SECONDARY · timing-neutral):  Resource sharing
    - Target: duplicate operator instances
    - Accepted only when timing slack unchanged
```

### Reject Set

- Any patch worsening WNS by more than 20 ps
- Any patch creating inferred latches
- Any patch touching `frozen_scope`

## Scope Semantics

```
allowed_edit_scope:
  rtl/{target_module}/**/*.sv

frozen_scope:
  rtl/common/**
  rtl/pkg/**
  rtl/intf/**
```

Every iteration runs `validate_patch_scope.py` on the generated `patch.diff`.
Violation → rollback (`git checkout .`) + halt.

## Rollback Protocol

All of these trigger rollback + halt:

- Patch touches `frozen_scope`
- Equivalence check FAIL
- Smoke regression FAIL
- Timing regression > 20 ps (Δ_wns < −0.02 ns)

Rollback is implemented as `git checkout .` in the target RTL scope. Prior to
the loop starting, the skill asserts a clean working tree.

## DC Tcl Fragment

See `templates/dc-compile-ppa.tcl`. Sourced by `run_syn.sh --tool dc_shell` via
the `--extra-script` option when `PPA_OPT_MODE=1`.

## PPA Brief Scaffold

When `requirements.json` is missing `ppa_targets`, the skill writes back the
content of `templates/ppa-brief-scaffold.json` and halts with user prompt.

## Early-Plateau Escalation Report Template

```markdown
# reviews/ppa-opt/early-plateau-escalation.md

## Verdict: EARLY_PLATEAU

EDA tool auto-optimization appears saturated; RTL-level patches yielded
< {early_plateau_pct}% weighted improvement over the observed iterations.

## Iteration history

| iter | wns_ns | power_mw | area_um2 | weighted_Δ |
|------|--------|----------|----------|------------|
| ...  | ...    | ...      | ...      | ...        |

## Current bottleneck (from latest ppa-report.json)

- Critical path: {from} → {to} (slack {slack_ns} ns, {logic_levels} logic levels)
- Power hotspot: {group} {pct}%, clock network {clock_pct}%
- Clock gating efficiency: {gating_efficiency_pct}%

## Recommended user actions

1. Review μArch (pipeline depth, algorithm variant)
2. Relax spec targets (clock / power budget)
3. Evaluate technology changes (stdcell library, Vt mix)
4. Force continuation via:
   requirements.json["ppa_targets"]["convergence"]["max_cycles"] = N  (N > 4)
```

## References

- Synopsys Design Compiler User Guide — `compile_ultra`, `set_clock_gating_style`
- Synopsys Power Compiler User Guide — `set_power_opt`, `report_power -analysis_effort`
- Weste & Harris, *CMOS VLSI Design* — clock gating methodology
```

- [ ] **Step 5.5: Verify frontmatter parses cleanly**

```bash
python3 -c "import pathlib, re; text=pathlib.Path('skills/ppa-optimizer-dc-policy/SKILL.md').read_text(); m=re.match(r'---\n(.*?)\n---', text, re.DOTALL); assert m, 'no frontmatter'; print('OK')"
```
Expected: `OK`

- [ ] **Step 5.6: Commit**

```bash
git add skills/ppa-optimizer-dc-policy/
git commit -m "feat(ppa): add ppa-optimizer-dc-policy skill with timing-first heuristic"
```

---

## Task 6: Agent — ppa-optimizer-dc (RTL Patcher)

**Files:**
- Create: `agents/ppa-optimizer-dc.md`

- [ ] **Step 6.1: Write agent prompt**

Write this content to `agents/ppa-optimizer-dc.md`:

```markdown
---
name: ppa-optimizer-dc
description: DC-based PPA optimization RTL patcher. Reads ppa-report.json + RTL + requirements.json, emits RTL unified diff + rationale + DC Tcl snippet. Timing-first heuristic. Never modifies files outside allowed_edit_scope.
model: opus
color: orange
skills:
  - ppa-optimizer-dc-policy
  - systemverilog
---

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

<Agent_Prompt>
  <Role>
    You are the PPA Optimizer. You analyze a Design Compiler `ppa-report.json`
    and the current RTL source, then propose a minimal RTL patch that improves
    power / timing / area according to policy weights. You do not modify files
    outside `allowed_edit_scope`. You do not worsen timing beyond the 20 ps
    regression guard. You produce: (a) unified diff, (b) rationale document,
    (c) optional DC Tcl snippet.

    Your analysis follows the **lowRISC SystemVerilog Coding Style Guide** with
    project overrides:
    - Port prefix `i_`, `o_`, `io_` (NOT suffix)
    - Clock `clk` / `{domain}_clk`, reset `rst_n` / `{domain}_rst_n` (active-low async)
    - Use `logic` everywhere; no `reg` / `wire`
    - `typedef enum` for FSMs, `typedef struct packed` for bundles
    - Instance prefix `u_`, generate prefix `gen_`
    - Parameters `ALL_CAPS`, localparam `L_` prefix

    All heuristic rules and thresholds live in the `ppa-optimizer-dc-policy`
    skill. Consult it for weights, convergence thresholds, optimization
    priorities, and DC Tcl fragments.
  </Role>

  <Why_This_Matters>
    EDA synthesis tools already perform exhaustive logic optimization and auto
    clock-gating insertion. LLM-generated RTL patches add value only where RTL
    structure prevents the tool from reaching a better solution: a register
    bank that lacks an enable signal, a multiplier whose operands toggle during
    idle cycles, a combinational cloud deeper than the pipeline budget. A
    patch that worsens timing, inserts a latch, or touches frozen interfaces
    is worse than no patch — this agent is conservative by design.
  </Why_This_Matters>

  <Success_Criteria>
    - `patch.diff` is a valid unified diff applicable with `git apply`
    - Every touched file is under `allowed_edit_scope`; none under `frozen_scope`
    - Patch obeys coding conventions (port prefix, logic-only, no latch inference)
    - `rationale.md` explains the PPA report analysis and per-change justification
    - Expected PPA delta is stated with signed values for each axis (timing / power / area)
    - Optional `dc-tcl-snippet.tcl` contains only ADDITIONAL constraints beyond the
      standard PPA compile fragment (never replaces the base compile strategy)
  </Success_Criteria>

  <Constraints>
    - NEVER touch files under `frozen_scope` (rtl/common/**, rtl/pkg/**, rtl/intf/**)
    - NEVER worsen WNS by more than 20 ps; such patches are rejected by the loop
    - NEVER introduce inferred latches; every `always_comb` must fully assign its outputs
    - Prefer minimal patches: small hunks are easier to verify for equivalence
    - Output format is STRICT: `patch.diff` + `rationale.md` + optional `dc-tcl-snippet.tcl`
    - Do NOT call `Write` on files outside the target iteration directory (`docs/ppa-opt/iter-{N}/`)
      unless explicitly directed. RTL edits go through the diff, not direct writes
  </Constraints>

  <Investigation_Protocol>
    1. Read the iteration context:
       - `requirements.json["ppa_targets"]` for weights, targets, max_fanout, max_transition
       - `syn/ppa-report.json` (current iteration) and `docs/ppa-opt/iter-{N-1}/ppa-report.json` if present
       - `.rat/state/ppa-loop-state.json` for allowed_edit_scope, frozen_scope, history
    2. Identify the top 3 bottlenecks ranked by weighted contribution:
       - Timing: paths with `slack_ns < 0`, sorted by `slack_ns` ascending
       - Power: top-contributing modules by `per_module[*].pct`; clock network %
       - Area: top-contributing modules by `per_module[*].pct`
    3. For each bottleneck, classify the root cause:
       - Timing → logic level depth, carry chain length, MUX fanout, critical operator
       - Power → missing clock gate, unisolated operand, excessive toggling net
       - Area → redundant logic, wide MUX tree, unshared operators
    4. Cross-check against the policy heuristic priority: Rule 1 (timing) first,
       then Rule 2 (clock gating), then timing-neutral Rule 3/4.
    5. Draft the smallest RTL change that addresses the highest-priority bottleneck
       without violating REJECT rules.
    6. Verify the change respects coding conventions (no `reg`/`wire`, proper prefixes,
       no latch risk).
    7. Generate the patch, rationale, and optional DC Tcl snippet.
  </Investigation_Protocol>

  <Tool_Usage>
    - Read: ppa-report.json, requirements.json, RTL files, policy skill
    - Grep: locate specific signals / modules referenced in critical paths
    - Write: patch.diff, rationale.md, dc-tcl-snippet.tcl in docs/ppa-opt/iter-{N}/

    Typical iteration:
    ```
    Read docs/ppa-opt/iter-{N}/ppa-report.json
    Read requirements.json
    Read .rat/state/ppa-loop-state.json
    Read rtl/{target_module}/**/*.sv (via Glob + Read)
    ... analyze ...
    Write docs/ppa-opt/iter-{N}/patch.diff
    Write docs/ppa-opt/iter-{N}/rationale.md
    Write docs/ppa-opt/iter-{N}/dc-tcl-snippet.tcl  (optional)
    ```
  </Tool_Usage>

  <Output_Format>
    ## `patch.diff`
    Valid unified diff (`git apply`-compatible). Use full context (3 lines).
    Every hunk must correspond to a reasoning entry in the rationale.

    ## `rationale.md`
    ```markdown
    # PPA Patch Rationale — Iteration {N}

    ## PPA Report Summary
    - Total power: {mw} mW  (dyn {dyn_mw} / leak {leak_mw})
    - WNS: {wns_ns} ns  (target slack {target_slack_ns} ns)
    - TNS: {tns_ns} ns over {n_violating} violating paths
    - Total area: {area_um2} um2
    - Clock gating efficiency: {eff}%
    - Vt mix: LVT {lvt_pct}% / SVT {svt_pct}% / HVT {hvt_pct}%

    ## Bottleneck Analysis (top 3)
    | Rank | Axis | Location | Root Cause | Weighted Contribution |
    |------|------|----------|------------|-----------------------|

    ## Proposed Changes
    ### Change 1: {title}
    - File: `rtl/...sv:{line_range}`
    - Rule applied: Rule {N} ({Timing / Clock Gating / Operand Isolation / Resource Sharing})
    - Root cause addressed: {description}
    - Expected delta:
      - Δ WNS: {ns}
      - Δ Power: {mw}
      - Δ Area: {um2}
    - Verification note: {why this preserves equivalence}

    ## Expected Weighted Δ
    - Weights: {w_timing} / {w_power} / {w_area}
    - Combined: {weighted_delta_pct} %

    ## Non-obvious Assumptions
    - {any assumption the reviewer should verify}
    ```

    ## `dc-tcl-snippet.tcl` (optional)
    Only include when the change benefits from additional DC constraints
    (e.g., a new `set_multicycle_path`). Must be additive, not replacing
    `templates/dc-compile-ppa.tcl`.
  </Output_Format>

  <Failure_Modes_To_Avoid>
    - Modifying interface/package files (frozen_scope)
    - Introducing inferred latches in an always_comb block
    - Moving registers across clock domain boundaries
    - Changing functional behavior (equivalence will fail; iteration wasted)
    - Using `reg`/`wire` keywords
    - Naming violations (CamelCase, suffix port naming)
    - Over-large patches that are hard to verify — prefer minimal targeted changes
    - Aggressive retiming that DC already tried — focus on RTL structure, not microscheduling
  </Failure_Modes_To_Avoid>

  <Examples>
    <Good>
      "Iteration 2 bottleneck: top/u_core/u_s1/pix_reg[7..0] has no enable signal
      (clock_gating.rpt: Ungated 32 regs at top/u_core/u_s1/stat_reg; similar
      pattern in pix_reg). Added `i_valid` enable gate in u_s1.sv:82-94. Expected
      Δ: clock_mw 42.10 → ~38.5 mW (-8.5%), timing unchanged."
    </Good>
    <Bad>
      "Improved the datapath."  — no file:line, no metric, no rule citation
    </Bad>
  </Examples>

  <Final_Checklist>
    - [ ] `patch.diff` applies cleanly with `git apply --check`
    - [ ] Every touched file under `allowed_edit_scope`
    - [ ] No file under `frozen_scope` touched
    - [ ] No `reg`/`wire` introduced; coding conventions intact
    - [ ] No latch risk in any `always_comb`
    - [ ] `rationale.md` explains each hunk
    - [ ] Expected PPA delta stated per axis
    - [ ] DC Tcl snippet (if any) is additive
  </Final_Checklist>
</Agent_Prompt>

## Team Worker Protocol

When spawned with `team_name`, follow `agents/lib/team-worker-preamble.md`.
When spawned as a Task() subagent by the orchestrator (traditional mode),
ignore the team protocol and work from the orchestrator's prompt directly.
```

- [ ] **Step 6.2: Verify frontmatter**

```bash
python3 -c "import pathlib,re; t=pathlib.Path('agents/ppa-optimizer-dc.md').read_text(); assert re.match(r'---\n(.*?)\n---',t,re.DOTALL); print('OK')"
```
Expected: `OK`

- [ ] **Step 6.3: Commit**

```bash
git add agents/ppa-optimizer-dc.md
git commit -m "feat(ppa): add ppa-optimizer-dc agent (RTL patcher, timing-first)"
```

---

## Task 7: Agent — dc-report-parser

**Files:**
- Create: `agents/dc-report-parser.md`

- [ ] **Step 7.1: Write agent prompt**

Write this content to `agents/dc-report-parser.md`:

```markdown
---
name: dc-report-parser
description: Thin wrapper around skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py. Invokes the parser on syn/rpt/ and returns syn/ppa-report.json location plus a terse JSON summary. No RTL modification.
model: sonnet
color: cyan
disallowedTools: Edit, Write
---

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

<Agent_Prompt>
  <Role>
    You are the DC Report Parser. You invoke `parse_dc_reports.py` on the
    `syn/rpt/` directory (after `run_syn.sh --tool dc_shell` has written the
    reports) and produce `syn/ppa-report.json` plus a short textual summary for
    the orchestrator. You do not modify any files directly (the script writes
    the JSON). You do not analyze the content — that is the
    `ppa-optimizer-dc` agent's role.
  </Role>

  <Success_Criteria>
    - `syn/ppa-report.json` exists and is valid JSON
    - `schema_version`, `tool`, `design`, `iteration` are populated
    - Top-level sections (area, timing, power, qor, clock_gating, vt_group) exist
    - Terse textual summary printed for the orchestrator: WNS, TNS, total power,
      total area, clock gating efficiency, critical path from→to
  </Success_Criteria>

  <Constraints>
    - Do NOT modify RTL, SDC, Tcl, or any file outside `syn/`.
    - Do NOT hand-parse .rpt files — always delegate to `parse_dc_reports.py`.
    - If the parser fails, capture stderr verbatim and return it to the orchestrator.
  </Constraints>

  <Investigation_Protocol>
    1. Ensure `syn/rpt/` exists and contains at least area / timing / qor reports.
    2. Set the annotation environment variables before invoking the script:
       - `PPA_TOOL` (dc_shell or genus)
       - `PPA_TOP` (top module name from requirements.json or CLI)
       - `PPA_ITER` (current iteration index from .rat/state/ppa-loop-state.json)
       - `PPA_LIBERTY` (from syn/scr/ generated script or rat_config.json)
       - `PPA_SDC` (syn/constraints/design.sdc or custom)
    3. Invoke:
       ```
       python3 skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py \
         syn/rpt/ syn/ppa-report.json
       ```
    4. Validate the output: load JSON, assert required keys present.
    5. Emit the terse summary to stdout.
  </Investigation_Protocol>

  <Tool_Usage>
    - Bash: run parse_dc_reports.py, set env vars
    - Read: syn/ppa-report.json for validation
    - Do NOT use Edit, Write
  </Tool_Usage>

  <Output_Format>
    ```
    ppa-report.json: syn/ppa-report.json (iteration N)
    - WNS: {wns_ns} ns  TNS: {tns_ns} ns  (status: {status})
    - Total power: {total_mw} mW  (dyn {dyn}/leak {leak}/clock {clock_pct}%)
    - Total area: {area_um2} um2
    - Clock gating efficiency: {eff}%
    - Worst path: {from} → {to} ({slack_ns} ns)
    - Warnings: {count}
    ```
  </Output_Format>

  <Final_Checklist>
    - [ ] parse_dc_reports.py exited 0
    - [ ] syn/ppa-report.json is valid JSON with all required sections
    - [ ] Terse summary emitted to orchestrator
  </Final_Checklist>
</Agent_Prompt>

## Team Worker Protocol

When spawned with `team_name`, follow `agents/lib/team-worker-preamble.md`.
Otherwise, ignore the team protocol and work from the orchestrator prompt.
```

- [ ] **Step 7.2: Commit**

```bash
git add agents/dc-report-parser.md
git commit -m "feat(ppa): add dc-report-parser agent (parser wrapper)"
```

---

## Task 8: Agent — ppa-optimizer-dc-orchestrator

**Files:**
- Create: `agents/ppa-optimizer-dc-orchestrator.md`

- [ ] **Step 8.1: Write orchestrator prompt**

Write this content to `agents/ppa-optimizer-dc-orchestrator.md`:

```markdown
---
name: ppa-optimizer-dc-orchestrator
description: Coordinator for one PPA optimization iteration. Sequences DC synthesis, report parsing, RTL patching, equivalence, smoke regression, delta computation, and convergence verdict. Self-contained; spawned by rtl-ppa-optimize-dc or rat-ultraloop-ppa skill.
model: opus
color: purple
skills:
  - ppa-optimizer-dc-policy
  - syn-tool-profiles
---

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

<Agent_Prompt>
  <Role>
    You are the PPA Optimizer Orchestrator. For a single iteration you run:
    DC synthesis → report parsing → RTL patch proposal → scope validation →
    equivalence check → smoke regression → re-synthesis → Δ computation →
    convergence verdict. You never modify RTL directly — that is the
    `ppa-optimizer-dc` agent's role. You dispatch subagents via `Task()` and
    interpret their results.
  </Role>

  <Step_0_Context_Bootstrap>
    ```
    Read .claude/rules/rtl-coding-conventions.md    (setup marker check)
    Read .rat/state/ppa-loop-state.json              (cycle, scope, history)
    Read requirements.json                           (ppa_targets, weights)
    Read reviews/phase-5-verify/final-compliance.md  (prereq check; advisory)
    ```
    If `.claude/rules/rtl-coding-conventions.md` is missing, halt with:
    "SETUP MISSING — run rat-init-project first".

    If `.rat/state/ppa-loop-state.json` is missing, halt with:
    "PPA loop state not initialized — invoke via rtl-ppa-optimize-dc or rat-ultraloop-ppa skill".
  </Step_0_Context_Bootstrap>

  <Preconditions>
    - `dc_shell` OR `genus` available in PATH
    - `requirements.json["ppa_targets"]` populated
    - Git working tree clean under `allowed_edit_scope`
    - `syn/scripts/run_syn.sh` exists (deployed by rat-init-project)
  </Preconditions>

  <Single_Iteration_Protocol>
    ### Step 1: DC synthesis (current RTL)

    `run_syn.sh` supports `--script <tcl>` for a full custom Tcl (bypassing
    auto-generation). The orchestrator composes a thin wrapper Tcl that does
    the standard DC setup, then sources the policy-owned compile fragment:

    ```bash
    mkdir -p syn/scr
    cat > syn/scr/dc-ppa-wrapper.tcl <<TCL
    set top ${PPA_TOP}
    set_app_var search_path "syn/scr \$search_path"
    set_app_var link_library "* ${PPA_LIBERTY}"
    set_app_var target_library "${PPA_LIBERTY}"

    define_design_lib WORK -path syn/work
    analyze  -format sverilog -library WORK -f sverilog \
             -file_list rtl/filelist_${PPA_TOP}.f
    elaborate \$top -library WORK
    current_design \$top
    link

    read_sdc ${PPA_SDC}

    source skills/ppa-optimizer-dc-policy/templates/dc-compile-ppa.tcl

    write -format ddc     -hierarchy -output syn/db/\${top}.ddc
    write -format verilog -hierarchy -output syn/vnet/\${top}.v
    exit
    TCL

    syn/scripts/run_syn.sh \
        --tool ${PPA_TOOL:-dc_shell} \
        --top ${PPA_TOP} \
        -f rtl/filelist_${PPA_TOP}.f \
        --liberty ${PPA_LIBERTY} \
        --script syn/scr/dc-ppa-wrapper.tcl
    ```
    Expected: `syn/rpt/{area,timing,power,qor,clock_gating,vt}.rpt` written.
    Failure: halt with the log path; do not proceed.

    ### Step 2: Parse reports → ppa-report.json
    ```
    Task(subagent_type="rtl-agent-team:dc-report-parser",
         description=f"Parse DC reports for iteration {N}",
         prompt="Invoke parse_dc_reports.py on syn/rpt/ with PPA_ITER={N}, PPA_TOP={top}, PPA_TOOL={tool}.")
    ```
    Copy `syn/ppa-report.json` → `docs/ppa-opt/iter-{N}/ppa-report.json`.

    ### Step 3: Snapshot pre-patch RTL
    ```bash
    git stash create  # reference for potential rollback
    ```

    ### Step 4: Generate RTL patch
    ```
    Task(subagent_type="rtl-agent-team:ppa-optimizer-dc",
         description=f"Generate PPA patch for iteration {N}",
         prompt="Read docs/ppa-opt/iter-{N}/ppa-report.json and requirements.json. "
                "Generate patch.diff + rationale.md + optional dc-tcl-snippet.tcl "
                "into docs/ppa-opt/iter-{N}/. Respect allowed_edit_scope from "
                ".rat/state/ppa-loop-state.json.")
    ```

    ### Step 5: Scope validation
    ```bash
    python3 skills/rtl-ppa-optimize-dc/scripts/validate_patch_scope.py \
        docs/ppa-opt/iter-{N}/patch.diff \
        "rtl/${PPA_TOP}/**/*.sv" \
        "rtl/common/**,rtl/pkg/**,rtl/intf/**"
    ```
    Non-zero exit → halt, do not apply.

    ### Step 6: Apply patch
    ```bash
    git apply --check docs/ppa-opt/iter-{N}/patch.diff && \
    git apply docs/ppa-opt/iter-{N}/patch.diff
    ```
    Failure → halt with the git error.

    ### Step 7: Equivalence check
    ```
    Task(subagent_type="rtl-agent-team:equivalence-checker",
         description=f"Equivalence check iter {N}",
         prompt="Compare current RTL (with PPA patch applied) against snapshot "
                "at iter-{N-1} (or HEAD~1 for iter-1). Blackbox rtl/common/sram_*. "
                "Report EQUIVALENT or NOT_EQUIVALENT with counterexample.")
    ```
    On NOT_EQUIVALENT: `git checkout .`, write `reviews/ppa-opt/equiv-fail-iter-{N}.md`, halt.

    ### Step 8: Smoke regression
    ```bash
    if [ -f sim/${PPA_TOP}/Makefile ]; then
        make -C sim/${PPA_TOP} smoke 2>&1 | tee docs/ppa-opt/iter-{N}/smoke.log
    else
        echo "WARNING: no smoke target for ${PPA_TOP}" >&2
    fi
    ```
    Non-zero exit → `git checkout .`, write `reviews/ppa-opt/smoke-fail-iter-{N}.md`, halt.

    ### Step 9: Re-synthesis (post-patch)
    Same as Step 1, write to iter-{N} directory.

    ### Step 10: Timing regression guard
    Compare WNS (post-patch) vs. WNS (pre-patch). If `Δ_wns < -0.02 ns`:
    `git checkout .`, write `reviews/ppa-opt/timing-regression-iter-{N}.md`, halt.

    ### Step 11: Delta computation & convergence verdict
    ```bash
    python3 skills/rtl-ppa-optimize-dc/scripts/compute_delta.py \
        docs/ppa-opt/iter-{N}/ppa-report.json \
        .rat/state/ppa-loop-state.json \
        requirements.json
    ```
    Output ∈ {CONTINUE, CONVERGED_STREAK, CONVERGED_TARGETS, EARLY_PLATEAU, MAX_CYCLES}.
    Write the verdict to `docs/ppa-opt/iter-{N}/verdict.txt`.

    ### Step 12: Append to convergence.csv
    ```bash
    {
      iter_entry=$(python3 -c "import json; s=json.load(open('.rat/state/ppa-loop-state.json')); h=s['convergence']['history'][-1]; print(','.join(str(h.get(k, '')) for k in ['iter','wns_ns','power_mw','area_um2','weighted_delta_pct']))")
      echo "$iter_entry" >> docs/ppa-opt/convergence.csv
    }
    ```
  </Single_Iteration_Protocol>

  <Output_Format>
    ```
    ## Iteration {N} verdict: {CONTINUE|CONVERGED_*|EARLY_PLATEAU|MAX_CYCLES}
    - WNS: {wns} ns  (Δ {d_wns} ns)
    - Power: {mw} mW  (Δ {d_mw} mW)
    - Area: {um2} um2  (Δ {d_um2} um2)
    - Weighted Δ: {pct}%
    - Current streak: {k}/{streak_required}
    - Next: {continue | halt | finalize}
    ```
  </Output_Format>

  <Failure_Modes_To_Avoid>
    - Proceeding when `dc_shell`/`genus` is absent (Precondition check missing)
    - Running equivalence against the post-patch RTL as reference (always use pre-patch)
    - Accepting patches that violate scope (must run validate_patch_scope.py)
    - Ignoring timing regression guard
    - Mutating `.rat/state/ppa-loop-state.json` by hand — always go through compute_delta.py
  </Failure_Modes_To_Avoid>

  <Final_Checklist>
    - [ ] Step 0 context bootstrap verified setup markers
    - [ ] DC synthesis succeeded with extra Tcl fragment loaded
    - [ ] ppa-report.json produced and copied to iter-{N}/
    - [ ] Patch generated, scope-validated, applied
    - [ ] Equivalence PASS
    - [ ] Smoke PASS (or WARNING documented)
    - [ ] Re-synthesis succeeded
    - [ ] Timing regression guard observed
    - [ ] Convergence verdict written
    - [ ] convergence.csv appended
  </Final_Checklist>
</Agent_Prompt>
```

- [ ] **Step 8.2: Commit**

```bash
git add agents/ppa-optimizer-dc-orchestrator.md
git commit -m "feat(ppa): add ppa-optimizer-dc-orchestrator (iteration coordinator)"
```

---

## Task 9: Action Skill — rtl-ppa-optimize-dc

**Files:**
- Create: `skills/rtl-ppa-optimize-dc/SKILL.md`

- [ ] **Step 9.1: Write SKILL.md**

Write this content to `skills/rtl-ppa-optimize-dc/SKILL.md`:

```markdown
---
name: rtl-ppa-optimize-dc
description: "One-shot Design Compiler–based PPA optimization iteration. Runs DC synthesis, parses reports into JSON, generates RTL patch, validates scope, verifies equivalence + smoke, computes delta, and emits convergence verdict. Requires Phase 5 PASS and dc_shell/genus in PATH."
user-invocable: true
argument-hint: "[top-module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, Skill
---

<Purpose>
Execute ONE iteration of the DC-based PPA optimization loop against a verified
RTL design. Produces `docs/ppa-opt/iter-{N}/` with the synthesis reports, RTL
patch, equivalence/smoke evidence, and a convergence verdict. For automated
iteration until convergence, use `rat-ultraloop-ppa` instead.
</Purpose>

<Use_When>
- User says "PPA optimize", "DC PPA", "power/timing/area optimize"
- A single exploratory PPA iteration is desired
- Debugging the PPA loop mechanics without auto-continue
</Use_When>

<Do_Not_Use_When>
- Phase 5 verification has not passed (use rtl-p5-verify first)
- No `dc_shell` nor `genus` available (this skill hard-fails)
- Full automatic iteration is wanted (use `rat-ultraloop-ppa`)
- RTL still under active development (finish Phase 4 first)
</Do_Not_Use_When>

## Prerequisites

- `reviews/phase-5-verify/final-compliance.md` verdict=PASS (soft advisory —
  warns and proceeds if absent)
- `dc_shell` OR `genus` in PATH (HARD — fail on absence)
- `requirements.json["ppa_targets"]` populated (HARD — writeback scaffold and halt)
- Git working tree clean under `allowed_edit_scope`
- `syn/scripts/run_syn.sh` deployed by `rat-init-project`

## Invocation

```
/rtl-agent-team:rtl-ppa-optimize-dc [top_module]
```

When `top_module` is omitted, reads from `requirements.json["top_module"]`.

## Execution

```
# Step 1: Bootstrap ppa-loop-state.json if absent
if not exists(".rat/state/ppa-loop-state.json"):
    Write(".rat/state/ppa-loop-state.json", initial_state(
        target_module=ARGUMENTS or requirements.top_module,
        max_cycles=requirements.ppa_targets.convergence.max_cycles or 4
    ))

# Step 2: Check preconditions (fail fast)
assert shutil_which("dc_shell") or shutil_which("genus"), \
    "Commercial synthesis (dc_shell or genus) required"
assert git_clean_under(allowed_edit_scope), \
    "Working tree must be clean; commit or stash first"

# Step 3: Advance cycle counter
state.cycle += 1
Write(".rat/state/ppa-loop-state.json", state)

# Step 4: Dispatch orchestrator
Task(subagent_type="rtl-agent-team:ppa-optimizer-dc-orchestrator",
     description=f"PPA iteration {state.cycle}",
     prompt="Execute one PPA optimization iteration. Read .rat/state/ppa-loop-state.json for scope and history.")
```

Do not perform per-iteration work directly. The orchestrator handles all
synthesis / parsing / patching / equivalence / convergence.

## Completion

The skill reports the verdict returned by the orchestrator. If verdict is
`CONVERGED_STREAK` or `CONVERGED_TARGETS`:
- Write `.rat/state/rtl-verify-done` (Rule 5 satisfaction marker)
- Write `.rat/state/ppa-opt-done` (P6 cascade trigger)
- Recommend `rtl-p5-verify` for full regression confirmation

Otherwise, the skill returns the verdict and exits. For `CONTINUE`, the user
invokes again or switches to `rat-ultraloop-ppa`.
```

- [ ] **Step 9.2: Commit**

```bash
git add skills/rtl-ppa-optimize-dc/SKILL.md
git commit -m "feat(ppa): add rtl-ppa-optimize-dc action skill (one-shot)"
```

---

## Task 10: Action Skill — rat-ultraloop-ppa

**Files:**
- Create: `skills/rat-ultraloop-ppa/SKILL.md`

- [ ] **Step 10.1: Write SKILL.md**

Write this content to `skills/rat-ultraloop-ppa/SKILL.md`:

```markdown
---
name: rat-ultraloop-ppa
description: "Auto-loop wrapper for DC-based PPA optimization. Repeats rtl-ppa-optimize-dc until convergence, early-plateau escalation, or max_cycles. 30-min auto-continue support. Emits final report + marks rtl-verify-done on normal convergence."
user-invocable: true
argument-hint: "[top-module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, Skill, AskUserQuestion
---

<Purpose>
Drive the DC-based PPA optimization loop to convergence. Wraps
`rtl-ppa-optimize-dc` in an auto-repeat loop with three termination tiers:
early plateau, normal convergence, max cycles. On normal convergence, runs
full Phase 5 regression and writes `rtl-verify-done` + `ppa-opt-done`.
</Purpose>

<Use_When>
- User says "ultraloop PPA", "PPA auto-loop", "optimize PPA until converge"
- Verified RTL ready for PPA refinement
- Industrial flow with dc_shell/genus available
</Use_When>

<Do_Not_Use_When>
- Preconditions of rtl-ppa-optimize-dc are not met
- User wants a single iteration only (use rtl-ppa-optimize-dc)
- Design is still under architectural change (freeze first)
</Do_Not_Use_When>

## Invocation

```
/rtl-agent-team:rat-ultraloop-ppa [top_module]
```

## Loop Body

```python
import json, time, shutil, subprocess, pathlib

TOP = ARGUMENTS or json.load(open("requirements.json"))["top_module"]

# Hard preconditions
assert shutil.which("dc_shell") or shutil.which("genus"), \
    "rat-ultraloop-ppa requires dc_shell or genus in PATH"

req = json.load(open("requirements.json"))
assert "ppa_targets" in req, \
    "requirements.json missing ppa_targets — run rtl-ppa-optimize-dc once to scaffold"

max_cycles = int(req["ppa_targets"].get("convergence", {}).get("max_cycles", 4))

# Initialize state
state_path = pathlib.Path(".rat/state/ppa-loop-state.json")
if not state_path.exists():
    state = {
        "mode": "ppa-loop",
        "cycle": 0,
        "max_cycles": max_cycles,
        "weights": req["ppa_targets"].get("weights", {"timing":0.7, "power":0.2, "area":0.1}),
        "convergence": {
            "delta_pct": req["ppa_targets"].get("convergence", {}).get("delta_pct", 2.0),
            "streak_required": req["ppa_targets"].get("convergence", {}).get("streak", 3),
            "early_plateau_pct": req["ppa_targets"].get("convergence", {}).get("early_plateau_pct", 1.0),
            "history": [],
        },
        "allowed_edit_scope": [f"rtl/{TOP}/**/*.sv"],
        "frozen_scope": ["rtl/common/**", "rtl/pkg/**", "rtl/intf/**"],
        "last_cycle_timestamp": int(time.time()),
        "auto_continue_minutes": 30,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))

# Iterate
for cycle in range(1, max_cycles + 1):
    verdict = Skill(skill="rtl-agent-team:rtl-ppa-optimize-dc", prompt=TOP)
    verdict = verdict.strip().splitlines()[-1].strip()

    if verdict in ("CONVERGED_STREAK", "CONVERGED_TARGETS"):
        # Full Phase 5 regression confirmation
        Skill(skill="rtl-agent-team:rtl-p5-verify", prompt="--mode=final --source=ppa-opt")
        pathlib.Path(".rat/state/rtl-verify-done").write_text(f"ppa-opt-converge cycle {cycle}\n")
        pathlib.Path(".rat/state/ppa-opt-done").write_text(f"converge cycle {cycle}\n")
        generate_final_report("CONVERGED", cycle)
        pathlib.Path(state_path).unlink()
        break

    if verdict == "EARLY_PLATEAU":
        generate_plateau_report(cycle)
        pathlib.Path(state_path).unlink()
        break

    if verdict == "MAX_CYCLES":
        generate_final_report("MAX_CYCLES", cycle)
        pathlib.Path(state_path).unlink()
        break

    # CONTINUE — next iteration
    continue

else:
    # Safety net (should not reach here due to MAX_CYCLES check above)
    generate_final_report("LOOP_EXIT_UNEXPECTED", cycle)
    pathlib.Path(state_path).unlink()
```

## Final Report (`docs/ppa-opt/final-report.md`)

```markdown
# PPA Optimization Final Report

- Target module: {TOP}
- Cycles executed: {N} / {max_cycles}
- Exit reason: CONVERGED | EARLY_PLATEAU | MAX_CYCLES

## Iteration history

| iter | wns_ns | power_mw | area_um2 | weighted_Δ |

## Best-so-far iteration
- iter: {best_iter}
- wns_ns: {}  power_mw: {}  area_um2: {}

## Next steps
- If CONVERGED: full Phase 5 regression passed → proceed to Phase 6 design note
- If EARLY_PLATEAU: see reviews/ppa-opt/early-plateau-escalation.md
- If MAX_CYCLES: consider raising max_cycles in requirements.json["ppa_targets"]["convergence"]
```

## 30-Min Auto-Continue

Reuses the `stop-gate.sh` escalation pattern: when
`.rat/state/ppa-loop-state.json` is present with `mode == "ppa-loop"` and
`last_cycle_timestamp + auto_continue_minutes*60 > now`, the hook auto-continues
instead of stopping.
```

- [ ] **Step 10.2: Commit**

```bash
git add skills/rat-ultraloop-ppa/SKILL.md
git commit -m "feat(ppa): add rat-ultraloop-ppa auto-loop wrapper"
```

---

## Task 11: Hook — rtl-edit-tracker.sh modification

**Files:**
- Modify: `hooks/rtl-edit-tracker.sh`

- [ ] **Step 11.1: Read the relevant region**

```bash
grep -n "rtl-modified" hooks/rtl-edit-tracker.sh | head -20
grep -n "^# " hooks/rtl-edit-tracker.sh | head -20
```

- [ ] **Step 11.2: Locate the staleness-accumulation block**

The tracker writes to `.rat/state/rtl-modified` when .sv/.svh/.v/.vh files change.
Find the main branch that sets that flag.

- [ ] **Step 11.3: Add PPA-loop skip guard**

Near the top of the script, after sourcing libraries, add:

```bash
# Skip staleness accumulation while a PPA-opt loop is active —
# every iteration's RTL edits are verified by equivalence + smoke inside the loop.
if [ -f ".rat/state/ppa-loop-state.json" ]; then
    mode=$(python3 -c "import json,sys; print(json.load(open('.rat/state/ppa-loop-state.json')).get('mode',''))" 2>/dev/null || echo "")
    if [ "$mode" = "ppa-loop" ]; then
        emit_continue "ppa-loop active — skipping rtl-edit staleness accumulation"
        exit 0
    fi
fi
```

Use the project's existing `emit_continue` helper from `hooks/lib/hook-output-util.sh`.

- [ ] **Step 11.4: Run shellcheck**

```bash
shellcheck hooks/rtl-edit-tracker.sh
```
Expected: no warnings.

- [ ] **Step 11.5: Commit**

```bash
git add hooks/rtl-edit-tracker.sh
git commit -m "fix(hooks): skip rtl-edit staleness during active PPA-opt loop"
```

---

## Task 12: Hook — stop-gate.sh modification

**Files:**
- Modify: `hooks/stop-gate.sh`

- [ ] **Step 12.1: Locate the existing ultraloop branch**

```bash
grep -n "ultraloop" hooks/stop-gate.sh
```

- [ ] **Step 12.2: Add ppa-loop branch mirroring the ultraloop auto-continue**

In the branch that handles `.rat/state/ultraloop-state.json`, add a parallel
branch for `.rat/state/ppa-loop-state.json`. The logic is identical:
check `mode == "ppa-loop"`, read `last_cycle_timestamp + auto_continue_minutes*60`,
and emit a continuation prompt if within the window.

Example insertion (exact location depends on the existing structure — mirror
the ultraloop case):

```bash
# PPA-Opt loop auto-continue (mirrors ultraloop)
if [ -f ".rat/state/ppa-loop-state.json" ]; then
    ppa_mode=$(python3 -c "import json; print(json.load(open('.rat/state/ppa-loop-state.json')).get('mode',''))" 2>/dev/null)
    if [ "$ppa_mode" = "ppa-loop" ]; then
        last_ts=$(python3 -c "import json; print(json.load(open('.rat/state/ppa-loop-state.json')).get('last_cycle_timestamp', 0))" 2>/dev/null || echo 0)
        auto_min=$(python3 -c "import json; print(json.load(open('.rat/state/ppa-loop-state.json')).get('auto_continue_minutes', 30))" 2>/dev/null || echo 30)
        now=$(date +%s)
        elapsed=$((now - last_ts))
        threshold=$((auto_min * 60))
        if [ "$elapsed" -lt "$threshold" ]; then
            emit_stop_block "PPA-Opt loop active (cycle pending, auto-continue in ${auto_min}m window). Use /oh-my-claudecode:cancel to halt."
            exit 0
        fi
    fi
fi
```

- [ ] **Step 12.3: shellcheck**

```bash
shellcheck hooks/stop-gate.sh
```

- [ ] **Step 12.4: Commit**

```bash
git add hooks/stop-gate.sh
git commit -m "feat(hooks): recognize ppa-loop mode in stop-gate for auto-continue"
```

---

## Task 13: Hook — rtl-p6-cascade-gate.sh modification

**Files:**
- Modify: `hooks/rtl-p6-cascade-gate.sh`

- [ ] **Step 13.1: Locate the cascade detection block**

```bash
grep -n "cascade\|stale\|p6" hooks/rtl-p6-cascade-gate.sh | head -30
```

- [ ] **Step 13.2: Add ppa-opt-done awareness**

Add this detection near the existing staleness check:

```bash
# If PPA optimization finished after P6 artifacts were written, flag re-review.
if [ -f ".rat/state/ppa-opt-done" ]; then
    ppa_mtime=$(get_mtime_epoch ".rat/state/ppa-opt-done" 2>/dev/null || echo 0)
    if [ -f "reviews/phase-6-review/design-note.md" ]; then
        p6_mtime=$(get_mtime_epoch "reviews/phase-6-review/design-note.md" 2>/dev/null || echo 0)
        if [ "$ppa_mtime" -gt "$p6_mtime" ]; then
            emit_stop_block "RTL modified by PPA-Opt loop after Phase 6 design-note — re-run rtl-p6-design-review."
            exit 0
        fi
    fi
fi
```

Use the project's `get_mtime_epoch` helper from `hooks/lib/posix-util.sh`.

- [ ] **Step 13.3: shellcheck**

```bash
shellcheck hooks/rtl-p6-cascade-gate.sh
```

- [ ] **Step 13.4: Commit**

```bash
git add hooks/rtl-p6-cascade-gate.sh
git commit -m "feat(hooks): cascade Phase 6 re-review after PPA-Opt completion"
```

---

## Task 14: Registry Updates

**Files:**
- Modify: `skill-completion-criteria.json`
- Modify: `phase-registry.json`

- [ ] **Step 14.1: Add completion criteria**

Open `skill-completion-criteria.json`. Add these entries in the skill map
(use the existing pattern):

```json
"rtl-ppa-optimize-dc": {
  "required_artifacts": [
    "docs/ppa-opt/iter-{N}/ppa-report.json",
    "docs/ppa-opt/iter-{N}/verdict.txt"
  ],
  "required_state": [
    ".rat/state/ppa-loop-state.json"
  ],
  "description": "One PPA iteration complete with verdict recorded"
},
"rat-ultraloop-ppa": {
  "required_artifacts": [
    "docs/ppa-opt/final-report.md"
  ],
  "required_state": [],
  "description": "PPA auto-loop finished with final report"
}
```

- [ ] **Step 14.2: Add phase-registry entries**

Open `phase-registry.json`. Add the `ppa-opt` phase and its mappings:

```json
"phases": {
  ...
  "ppa-opt": {
    "order": 5.5,
    "name": "Post-Verify PPA Optimization",
    "skills": ["rtl-ppa-optimize-dc", "rat-ultraloop-ppa"],
    "upstream": ["phase-5-verify"],
    "downstream": ["phase-6-design-note"]
  }
},
"skill_to_phase": {
  ...
  "rtl-ppa-optimize-dc": "ppa-opt",
  "rat-ultraloop-ppa": "ppa-opt"
},
"agent_to_skill": {
  ...
  "ppa-optimizer-dc-orchestrator": "rtl-ppa-optimize-dc",
  "ppa-optimizer-dc": "rtl-ppa-optimize-dc",
  "dc-report-parser": "rtl-ppa-optimize-dc"
}
```

- [ ] **Step 14.3: Validate JSON**

```bash
python3 -c "import json; json.load(open('skill-completion-criteria.json'))"
python3 -c "import json; json.load(open('phase-registry.json'))"
```
Expected: no output (valid JSON).

- [ ] **Step 14.4: Run registry sync tests**

```bash
python3 -m pytest tests/unit/test_phase_registry_sync.py -x -q 2>/dev/null || \
    echo "No phase-registry sync test present — skipping"
```
Expected: PASS or skip message.

- [ ] **Step 14.5: Commit**

```bash
git add skill-completion-criteria.json phase-registry.json
git commit -m "feat(ppa): register PPA skills in completion criteria + phase registry"
```

---

## Task 15: Routing SSOT Update

**Files:**
- Modify: `skills/rtl-orchestrate/SKILL.md`
- Modify: `hooks/rtl-orchestrator-inject.sh` (auto-regenerated)

- [ ] **Step 15.1: Read current routing table**

```bash
grep -n "Routing" skills/rtl-orchestrate/SKILL.md
```

- [ ] **Step 15.2: Add PPA routing entries**

Insert these rows in the routing table (between Phase 5 and Phase 6 entries):

```markdown
| PPA optimize, DC PPA, power/timing/area optimize | `/rtl-agent-team:rtl-ppa-optimize-dc` | Action Skill |
| PPA auto-loop, ultraloop PPA, converge PPA | `/rtl-agent-team:rat-ultraloop-ppa` | Action Skill |
```

- [ ] **Step 15.3: Regenerate the hook injection**

```bash
sh scripts/sync_orchestrator_inject.sh
```
Expected: `hooks/rtl-orchestrator-inject.sh` updated between `# BEGIN GENERATED` / `# END GENERATED` markers with the new routing rows.

- [ ] **Step 15.4: Confirm diff contains only the two new rows**

```bash
git diff hooks/rtl-orchestrator-inject.sh | grep -E "^\+" | grep -v "^+++" | head -10
```

- [ ] **Step 15.5: shellcheck the regenerated hook**

```bash
shellcheck hooks/rtl-orchestrator-inject.sh
```

- [ ] **Step 15.6: Commit**

```bash
git add skills/rtl-orchestrate/SKILL.md hooks/rtl-orchestrator-inject.sh
git commit -m "feat(ppa): add PPA skills to routing SSOT + regenerate injection"
```

---

## Task 16: CLAUDE.md Updates

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 16.1: Add Pipeline Rules 10 and 11**

In the Pipeline Rules table, insert after Rule 9:

```markdown
| 10 | Do not start DC-based PPA optimization without Phase 5 PASS | Policy — skill entry warning |
| 11 | Every PPA-Opt iteration must pass equivalence + smoke before accepting patch | Hard — `rat-ultraloop-ppa` internal guard (fail → rollback) |
```

- [ ] **Step 16.2: Add Post-Verify PPA note to the 6+1 Phase table**

After the Phase 7 line in the "6+1 Phase Design Pipeline" section, add:

```
(optional) Post-Verify PPA  → docs/ppa-opt/             (DC-based loop, between P5 and P6)
```

- [ ] **Step 16.3: Update component counts**

Find and update these phrases:
- "94 specialized agents" → "97 specialized agents"
- "94 skills" → "97 skills"
- Breakdown line: "54 action entry-points + 31 policies + 4 tool profiles + 4 conventions + 1 internal"
  → "56 action entry-points + 32 policies + 4 tool profiles + 4 conventions + 1 internal"

Rationale: this PR adds 2 action skills (`rtl-ppa-optimize-dc`, `rat-ultraloop-ppa`)
and 1 policy skill (`ppa-optimizer-dc-policy`), for +3 total.

Run a self-check first:

```bash
ls skills/*/SKILL.md | wc -l
ls agents/*.md | grep -v '^agents/lib/' | wc -l
```

Align the CLAUDE.md counts to the actual filesystem count (+3 skills total, +3 agents total from this PR).

- [ ] **Step 16.4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(ppa): add pipeline rules 10/11 + Post-Verify phase + count updates"
```

---

## Task 17: Version Bump (6-file batch)

**Files:**
- Modify: `package.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md`
- Modify: `README_kr.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 17.1: Use the bump-version script (dry-run first)**

```bash
sh scripts/bump-version.sh --dry-run 0.10.0
```
Expected: diff preview of all files — no write.

- [ ] **Step 17.2: Run bump for real**

```bash
sh scripts/bump-version.sh 0.10.0
```
Expected: all six files updated.

- [ ] **Step 17.3: Add CHANGELOG entry**

Edit `CHANGELOG.md`: move `[Unreleased]` items into a new `[0.10.0] - 2026-04-17` section and add:

```markdown
## [0.10.0] - 2026-04-17

### Added
- DC-based PPA optimization loop (Post-Verify stage between P5 and P6)
  - `rtl-ppa-optimize-dc` action skill (one-shot iteration)
  - `rat-ultraloop-ppa` auto-loop wrapper with 30-min auto-continue
  - `ppa-optimizer-dc-policy` reference skill (timing-first heuristic,
    default weights 0.7/0.2/0.1, convergence: streak 3 × |Δ|<2%,
    early-plateau at iter 1–2 × |Δ|<1%, default max_cycles=4)
  - New agents: `ppa-optimizer-dc-orchestrator`, `ppa-optimizer-dc`, `dc-report-parser`
  - `parse_dc_reports.py` — DC `.rpt` → `ppa-report.json` consolidation
  - `compute_delta.py` — weighted Δ + convergence verdict
  - `validate_patch_scope.py` — allowed/frozen scope enforcement for RTL patches
- Pipeline Rules 10 & 11 (policy; Rule 11 enforced inside wrapper)

### Changed
- `hooks/rtl-edit-tracker.sh` skips staleness during active PPA-opt loop
- `hooks/stop-gate.sh` recognizes `mode: "ppa-loop"` for auto-continue
- `hooks/rtl-p6-cascade-gate.sh` flags P6 re-review after `.rat/state/ppa-opt-done`
- `skills/rtl-orchestrate/SKILL.md` routing table extended with two entries
- Component counts: skills 94 → 97, agents 94 → 97

### Requirements
- Commercial synthesis required at runtime: `dc_shell` or `genus` in PATH
- `requirements.json["ppa_targets"]` section needed (scaffold auto-written on first run)
```

- [ ] **Step 17.4: Update README component counts and marketplace table**

In both `README.md` and `README_kr.md`:
- Marketplace table: version 0.9.3 → 0.10.0
- Breakdown lines: update the 94/94/14 figures to 97/97/14
- Add a one-line entry under the skills summary referring to the new PPA stage

- [ ] **Step 17.5: Cross-check no stale references**

```bash
grep -rn "0\.9\.3" package.json .claude-plugin/ README.md README_kr.md
```
Expected: no matches (all bumped to 0.10.0).

- [ ] **Step 17.6: Commit**

```bash
git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json \
        README.md README_kr.md CHANGELOG.md
git commit -m "chore(release): 0.10.0 — DC-based PPA optimization loop"
```

---

## Task 18: Integration Test

**Files:**
- Create: `tests/integration/test_ppa_loop_integration.py`

- [ ] **Step 18.1: Write the integration test**

Write this content to `tests/integration/test_ppa_loop_integration.py`:

```python
"""Integration test for PPA optimization loop state transitions.

Exercises compute_delta.py against a simulated history that goes through
CONTINUE → CONVERGED_STREAK. Does not require DC or git.
"""
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "rtl-ppa-optimize-dc" / "scripts"


def _write_report(path, wns, power, area):
    report = {
        "schema_version": "1.0",
        "tool": "dc_shell",
        "design": "stub",
        "iteration": 1,
        "timestamp": "2026-04-17T00:00:00Z",
        "liberty": "",
        "sdc": "",
        "area": {"total_um2": area, "per_module": []},
        "timing": {"clock": "sys_clk", "period_ns": 1.25, "wns_ns": wns,
                   "tns_ns": 0.0, "num_violating_paths": 0, "critical_paths": []},
        "power": {"total_mw": power, "dynamic_mw": power*0.8, "leakage_mw": power*0.2,
                  "clock_mw": power*0.33, "clock_pct": 33.0, "net_mw": 0, "register_mw": 0,
                  "combinational_mw": 0, "macro_mw": 0, "analysis_effort": "high", "per_module": []},
        "qor": {"design_wns_ns": wns, "design_tns_ns": 0, "worst_hold_slack_ns": 0, "status": "PASS"},
        "clock_gating": {"total_registers": 100, "gated_registers": 80, "gating_efficiency_pct": 80.0, "ungated_banks": []},
        "vt_group": {"LVT_pct": 5, "SVT_pct": 60, "HVT_pct": 35},
        "warnings": [],
    }
    pathlib.Path(path).write_text(json.dumps(report, indent=2))


def _initial_state(cycle=1, max_cycles=4):
    return {
        "mode": "ppa-loop",
        "cycle": cycle,
        "max_cycles": max_cycles,
        "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
        "convergence": {
            "delta_pct": 2.0,
            "streak_required": 3,
            "early_plateau_pct": 1.0,
            "history": [],
        },
        "allowed_edit_scope": ["rtl/stub/**/*.sv"],
        "frozen_scope": ["rtl/common/**"],
        "last_cycle_timestamp": 0,
        "auto_continue_minutes": 30,
    }


def _requirements():
    return {
        "top_module": "stub",
        "clock_hz": 800000000,
        "ppa_targets": {
            "power_mw": 100.0,
            "timing_slack_ns": 0.10,
            "area_um2": 50000.0,
            "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
            "convergence": {
                "delta_pct": 2.0,
                "streak": 3,
                "early_plateau_pct": 1.0,
                "max_cycles": 4,
            },
        },
    }


def _run_compute_delta(curr, state, req):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "compute_delta.py"),
         str(curr), str(state), str(req)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr


def test_loop_progression_to_streak_convergence(tmp_path):
    state = tmp_path / "state.json"
    req = tmp_path / "requirements.json"
    req.write_text(json.dumps(_requirements()))

    # --- iter 1: baseline
    s = _initial_state(cycle=1)
    state.write_text(json.dumps(s))
    curr = tmp_path / "iter1.json"
    _write_report(curr, -0.12, 135.0, 48000.0)
    rc, out, err = _run_compute_delta(curr, state, req)
    assert rc == 0, err
    assert out == "CONTINUE"

    # --- iter 2: small improvement (not yet converged)
    s = json.loads(state.read_text())
    s["cycle"] = 2
    state.write_text(json.dumps(s))
    curr = tmp_path / "iter2.json"
    _write_report(curr, -0.095, 130.0, 47500.0)
    rc, out, err = _run_compute_delta(curr, state, req)
    assert rc == 0, err
    assert out in ("CONTINUE", "EARLY_PLATEAU")

    # --- iter 3-4: small deltas — should reach CONVERGED_STREAK
    for cycle, (w, p, a) in [(3, (-0.094, 129.5, 47300.0)),
                              (4, (-0.093, 129.2, 47200.0))]:
        s = json.loads(state.read_text())
        s["cycle"] = cycle
        state.write_text(json.dumps(s))
        curr = tmp_path / f"iter{cycle}.json"
        _write_report(curr, *(w, p, a))
        rc, out, err = _run_compute_delta(curr, state, req)
        assert rc == 0, err
    # By iter 4 the streak should be met (three consecutive small deltas)
    final_state = json.loads(state.read_text())
    assert final_state["convergence"]["current_streak"] >= 2


def test_all_targets_met_triggers_converged_targets(tmp_path):
    state = tmp_path / "state.json"
    req = tmp_path / "requirements.json"
    req.write_text(json.dumps(_requirements()))
    s = _initial_state(cycle=2)
    state.write_text(json.dumps(s))
    curr = tmp_path / "targets_met.json"
    _write_report(curr, 0.05, 80.0, 44000.0)
    rc, out, err = _run_compute_delta(curr, state, req)
    assert rc == 0, err
    assert out == "CONVERGED_TARGETS"
```

- [ ] **Step 18.2: Run the integration test**

```bash
python3 -m pytest tests/integration/test_ppa_loop_integration.py -x -q
```
Expected: PASS.

- [ ] **Step 18.3: Commit**

```bash
git add tests/integration/test_ppa_loop_integration.py
git commit -m "test(ppa): add integration test for loop state transitions"
```

---

## Task 19: Full Verification Before Push

**Files:** none (verification only)

- [ ] **Step 19.1: Full pytest**

```bash
python3 -m pytest tests/unit/ tests/integration/ \
    --ignore=tests/unit/test_bd_rate.py -x -q
```
Expected: all tests PASS.

- [ ] **Step 19.2: shellcheck all hooks**

```bash
shellcheck hooks/*.sh hooks/lib/*.sh scripts/*.sh
```
Expected: no warnings.

- [ ] **Step 19.3: Verify registry sync**

```bash
python3 -m pytest tests/unit/test_mapping_sync_parity.py -x -q 2>/dev/null || true
python3 -m pytest tests/unit/test_phase_registry_sync.py -x -q 2>/dev/null || true
sh scripts/sync_orchestrator_inject.sh
git diff --exit-code hooks/rtl-orchestrator-inject.sh
```
Expected: pytest PASS (or skip); `git diff --exit-code` returns 0 (no uncommitted drift).

- [ ] **Step 19.4: Final commit if any regen needed**

If `sync_orchestrator_inject.sh` produced new changes:

```bash
git add hooks/rtl-orchestrator-inject.sh
git commit -m "chore(ppa): sync orchestrator injection after final verification"
```

---

## Task 20: Push

**Files:** none (git push only)

- [ ] **Step 20.1: Inspect local log**

```bash
git log --oneline origin/main..HEAD
```
Expected: 15-ish commits covering fixtures, parser, delta, scope guard, policy, agents, skills, hooks, registry, routing, version bump, integration test.

- [ ] **Step 20.2: Confirm branch state**

```bash
git status --porcelain
```
Expected: no output (clean tree).

- [ ] **Step 20.3: Push to main**

```bash
git push origin main
```
Expected: push succeeds; CI on `main` kicks off.

- [ ] **Step 20.4: Wait for CI — report status**

```bash
gh run list --branch main --limit 1
gh run watch
```
Expected: green (all jobs pass).

---

## Self-Review Checklist (for the implementer)

- [ ] Every task has a commit step
- [ ] Every code step shows the actual code (no placeholders)
- [ ] Every bash command shows expected output
- [ ] Scope respected: Write only to paths under `File Map`
- [ ] No hook adds logic bypassing an equivalence / smoke / scope check
- [ ] `rat-ultraloop-ppa` final report includes best-so-far iter
- [ ] Version bump batch updates every file listed in CLAUDE.md §14
- [ ] CI green before declaring done
