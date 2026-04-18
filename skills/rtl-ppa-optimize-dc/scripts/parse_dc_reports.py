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
        ("total_um2",          r"Total cell area:\s*([\d.eE+-]+)"),
        ("combinational_um2",  r"Combinational area:\s*([\d.eE+-]+)"),
        ("sequential_um2",     r"Noncombinational area:\s*([\d.eE+-]+)"),
        ("buf_inv_um2",        r"Buf/Inv area:\s*([\d.eE+-]+)"),
        ("macro_um2",          r"Macro/Black Box area:\s*([\d.eE+-]+)"),
    ]
    for key, pat in patterns:
        m = re.search(pat, text)
        if m:
            result[key] = float(m.group(1))
    hier_re = re.compile(
        r"^\s+([A-Za-z_][\w$]*(?:/[\w\[\]\.\$]+)*)\s+([\d.eE+-]+)\s+([\d.eE+-]+)%",
        re.MULTILINE,
    )
    for m in hier_re.finditer(text):
        hier, um2, pct = m.groups()
        # Skip the synthetic root row (depth 0 — no '/').
        # A legitimate single-child module at 100% is NOT a root, so do not
        # drop rows solely on pct; depth-0 alone identifies the synthetic root.
        if "/" not in hier:
            continue
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
    m = re.search(r"Clock\s+(\S+)\s+\(rise edge\)\s+at period\s+([\d.eE+-]+)", text)
    if m:
        result["clock"] = m.group(1)
        result["period_ns"] = float(m.group(2))
    else:
        m = re.search(r"clock\s+(\S+)\s+\(rise edge\)", text)
        if m:
            result["clock"] = m.group(1)
        m = re.search(r"Path Group:\s+(\S+).*?period\s+([\d.eE+-]+)", text, re.DOTALL)
        if m:
            result["period_ns"] = float(m.group(2))
    worst_slack = None
    for m in re.finditer(r"slack\s+\((?:VIOLATED|MET)\)\s+(-?[\d.eE+-]+)", text):
        slack = float(m.group(1))
        if worst_slack is None or slack < worst_slack:
            worst_slack = slack
    if worst_slack is not None:
        result["wns_ns"] = worst_slack
    path_re = re.compile(
        r"Startpoint:\s*(\S+).*?"
        r"Endpoint:\s*(\S+).*?"
        r"data arrival time\s+(-?[\d.eE+-]+).*?"
        r"slack\s+\((VIOLATED|MET)\)\s+(-?[\d.eE+-]+)",
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
        "internal_mw": 0.0,       # canonical name (schema 1.1)
        "register_mw": 0.0,       # legacy alias for internal_mw (schema 1.0 compatibility)
        "combinational_mw": 0.0,
        "macro_mw": 0.0,
        "per_module": [],
    }
    labels = [
        ("Total Dynamic Power", "dynamic_mw"),
        ("Cell Leakage Power",  "leakage_mw"),
        ("Net Switching Power", "net_mw"),
        ("Cell Internal Power", "internal_mw"),
        ("Total Power",         "total_mw"),
    ]
    for label, key in labels:
        m = re.search(
            rf"{re.escape(label)}\s*=\s*([\d.eE+-]+)\s*(\w+)",
            text,
        )
        if m:
            result[key] = _to_mw(float(m.group(1)), m.group(2))
    # Keep register_mw in sync with internal_mw for backward compatibility
    result["register_mw"] = result["internal_mw"]

    # Determine the per-table power unit from DC's "Dynamic Power Units" header
    # (Codex R14 M2). If the header is absent, DC defaults to mW so values in the
    # per-group and hierarchical tables are already in mW and the conversion is a no-op.
    _unit_m = re.search(r"Dynamic Power Units\s*=\s*\d*\s*(\w+)", text)
    power_unit = _unit_m.group(1) if _unit_m else "mW"

    group_re = re.compile(
        r"^(clock_network|register|combinational|black_box)\s+"
        r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+\(\s*([\d.eE+-]+)%\)",
        re.MULTILINE,
    )
    for m in group_re.finditer(text):
        group, _internal, _switching, _leakage, total, pct = m.groups()
        if group == "clock_network":
            result["clock_mw"] = _to_mw(float(total), power_unit)
            result["clock_pct"] = float(pct)
        elif group == "combinational":
            result["combinational_mw"] = _to_mw(float(total), power_unit)
    # Parse hierarchical power breakdown (from report_power -hier)
    hier_re = re.compile(
        r"^\s+([A-Za-z_][\w$]*(?:/[\w\[\]\.\$]+)*)"  # hierarchy path, any design top name
        r"\s+[\d.eE+-]+"                                # switch power
        r"\s+[\d.eE+-]+"                                # int power
        r"\s+[\d.eE+-]+"                                # leak power
        r"\s+([\d.eE+-]+)"                              # total power (captured)
        r"\s+([\d.eE+-]+)"                              # pct (captured)
        r"(?:\s+[A-Za-z][\w,]*)?"                  # optional Attrs column (letter+word chars+commas)
        r"\s*$",
        re.MULTILINE,
    )
    for m in hier_re.finditer(text):
        hier, total_mw, pct = m.groups()
        # Skip the synthetic root row (depth 0 — no '/'). A legitimate single-child
        # module at 100.00% is NOT a root and must be preserved.
        if "/" not in hier:
            continue
        result["per_module"].append({
            "hier": hier,
            "total_mw": _to_mw(float(total_mw), power_unit),
            "pct": float(pct),
        })
    return result


def parse_qor(path):
    if not path:
        return {}
    text = pathlib.Path(path).read_text()
    result = {
        "design_wns_ns": 0.0,
        "design_tns_ns": 0.0,
        "worst_hold_slack_ns": 0.0,
        "num_violating_paths": 0,
        "status": "PASS",
    }
    m = re.search(r"Design WNS:\s+(-?[\d.eE+-]+)", text)
    if m:
        result["design_wns_ns"] = float(m.group(1))
    m = re.search(r"Design TNS:\s+(-?[\d.eE+-]+)", text)
    if m:
        result["design_tns_ns"] = float(m.group(1))
    m = re.search(r"Worst Hold Slack:\s+(-?[\d.eE+-]+)", text)
    if m:
        result["worst_hold_slack_ns"] = float(m.group(1))
    m = re.search(r"No\.?\s+of\s+Violating\s+Paths:\s+([\d.eE+-]+)", text)
    if m:
        result["num_violating_paths"] = int(float(m.group(1)))
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
        m = re.search(rf"^{label}:\s*([\d.eE+-]+)\s*%", text, re.MULTILINE)
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
        "schema_version": "1.1",
        "tool": os.environ.get("PPA_TOOL", "dc_shell"),
        "design": os.environ.get("PPA_TOP", "unknown"),
        "iteration": int(os.environ.get("PPA_ITER", "0")),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
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

    # Cross-populate timing.tns_ns and timing.num_violating_paths from qor
    # (DC's report_timing does not include TNS; it lives in report_qor).
    qor = report.get("qor", {})
    timing = report.get("timing", {})
    if timing:
        if timing.get("tns_ns", 0.0) == 0.0 and qor.get("design_tns_ns") is not None:
            timing["tns_ns"] = qor["design_tns_ns"]
        if timing.get("num_violating_paths", 0) == 0:
            timing["num_violating_paths"] = qor.get("num_violating_paths", 0)

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
