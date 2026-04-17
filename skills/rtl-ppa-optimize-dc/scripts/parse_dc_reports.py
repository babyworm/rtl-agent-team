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
