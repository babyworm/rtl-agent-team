#!/usr/bin/env python3
"""Extract deterministic structure from a SystemVerilog module using Verible.

Output schema (top-level keys):
  module_name, file, parameters, ports, instances, fsm_candidates,
  clock_domains, convention_violations, synth_summary

Exit codes:
  0  success
  2  verible-verilog-syntax not on PATH
  3  SV parse error
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERIBLE_BIN = "verible-verilog-syntax"

PORT_RE = re.compile(
    r"^\s*(input|output|inout)\s+(?:logic|wire|reg)?\s*"
    r"(\[[^\]]+\])?\s*"
    r"([A-Za-z_][A-Za-z_0-9$\\]*)\s*(?=[,)]|$)",
)
# Trailing identifier(s) on the same declaration line, sharing the same
# direction + width as the leading port matched by PORT_RE.
# Example: `input logic [3:0] a, b, c,` → PORT_RE captures `a`, PORT_TRAIL_RE
# then picks up `b` and `c`.
PORT_TRAIL_RE = re.compile(
    r"\s*,\s*([A-Za-z_][A-Za-z_0-9$\\]*)\s*(?=[,)]|$)"
)


def _parse_width(width: str | None) -> str:
    """Parse an SV width declaration to a width expression.

    Accepted forms:
      - parametric:    [DATA_WIDTH-1:0]   → "DATA_WIDTH"
      - literal:       [31:0], [7:0], ... → "32", "8", ... (computed as hi-lo+1)
      - any non-zero-lo literal: [N:M]    → str(N-M+1)
    Anything else falls back to "1" (single bit / unable to parse).
    """
    if not width:
        return "1"
    # Parametric form: [<expr>-1:0]
    wm = re.match(r"\[\s*([^:]+)\s*-\s*1\s*:\s*0\s*\]", width)
    if wm:
        return wm.group(1).strip()
    # Literal form: [N:M]
    wm = re.match(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", width)
    if wm:
        hi, lo = int(wm.group(1)), int(wm.group(2))
        if hi >= lo:
            return str(hi - lo + 1)
    return "1"
PARAM_RE = re.compile(
    r"parameter\s+(?:int|integer|logic|bit|byte|real)?\s*"
    r"([A-Za-z_][A-Za-z_0-9]*)\s*=\s*([^,)\n]+)"
)
CLOCK_RE = re.compile(r"^(.+)_clk$")
RESET_RE = re.compile(r"^(.+)_rst_n$")
# Instance regex now accepts any valid SV identifier as the instance name.
# `_RESERVED` (used downstream) filters out keyword-starting lines such as
# `always_ff (...)`, `assign x = ...`, `if (cond) ...`, etc., so we don't
# misclassify control-flow constructs as module instances. Instances that
# violate the project's `u_*` naming convention are surfaced by the
# convention-violation pass rather than silently dropped.
INSTANCE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*(?:#\s*\((?:[^()]*|\([^()]*\))*\))?"
    r"\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(",
    re.MULTILINE,
)
SUFFIX_VIOLATION_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*_(i|o|io)$")

ENUM_RE = re.compile(
    r"typedef\s+enum\b[^{]*\{(?P<body>[^}]+)\}\s*(?P<type>[A-Za-z_][A-Za-z_0-9]*)\s*;",
    re.DOTALL,
)
STATE_REG_RE = re.compile(
    r"(?P<type>[A-Za-z_][A-Za-z_0-9]*)\s+(?P<name>[A-Za-z_][A-Za-z_0-9]*)\s*,\s*next_\w+\s*;",
)


def _check_violations(ports: list[dict]) -> list[dict]:
    violations = []
    for p in ports:
        if SUFFIX_VIOLATION_RE.match(p["name"]):
            violations.append({
                "signal": p["name"],
                "rule": "Use i_/o_/io_ prefix (not suffix)",
            })
    return violations


def _parse_synth_report(path: Path) -> dict:
    text = path.read_text()
    out: dict = {}
    m = re.search(r"Total cell area:\s*([0-9.]+)", text)
    if m:
        out["area_um2"] = float(m.group(1))
    m = re.search(r"WNS:\s*(-?[0-9.]+)", text)
    if m:
        out["wns_ns"] = float(m.group(1))
    m = re.search(r"TNS:\s*(-?[0-9.]+)", text)
    if m:
        out["tns_ns"] = float(m.group(1))
    m = re.search(r"Number of violating paths:\s*(\d+)", text)
    if m:
        out["num_violating_paths"] = int(m.group(1))
    return out


def find_verible() -> str | None:
    return shutil.which(VERIBLE_BIN)


def _classify(name: str) -> tuple[str, str | None]:
    m = CLOCK_RE.match(name)
    if m:
        return "clock", m.group(1)
    m = RESET_RE.match(name)
    if m:
        return "reset", m.group(1)
    return "data", None


def _verible_json(verible: str, rtl: str) -> dict:
    try:
        r = subprocess.run(
            [verible, "--export_json", rtl],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"_error": f"verible-verilog-syntax timed out after 30s on {rtl}"}
    if r.returncode != 0:
        # Some verible errors arrive on stdout instead of stderr.
        msg = r.stderr.strip() or r.stdout.strip() or f"exit={r.returncode}"
        return {"_error": msg}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {"_error": f"verible JSON decode error: {e}"}


def _parse_text(rtl_path: Path) -> dict:
    """Fallback regex-based parser; used standalone and to augment CST when fields missing."""
    text = rtl_path.read_text()
    module_name = rtl_path.stem
    m = re.search(r"module\s+([A-Za-z_][A-Za-z_0-9]*)\s*[#(]", text)
    if m:
        module_name = m.group(1)
    ports = []
    domains: set[str] = set()

    def _append_port(port_name: str, direction: str, width_str: str) -> None:
        kind, domain = _classify(port_name)
        if domain:
            domains.add(domain)
        ports.append({
            "name": port_name, "dir": direction, "width": width_str,
            "domain": domain or "?", "kind": kind,
        })

    for line in text.splitlines():
        pm = PORT_RE.match(line)
        if pm:
            direction, width, name = pm.group(1), pm.group(2), pm.group(3)
            width_str = _parse_width(width)
            _append_port(name, direction, width_str)
            # Pick up trailing identifiers on the same line that share the
            # leading port's direction + width (e.g. `input logic [3:0] a, b, c,`).
            rest = line[pm.end():]
            for tm in PORT_TRAIL_RE.finditer(rest):
                _append_port(tm.group(1), direction, width_str)
    params = [
        {"name": pm.group(1).strip(), "type": "int", "default": pm.group(2).strip()}
        for pm in PARAM_RE.finditer(text)
    ]
    # SV keywords that look like a "type identifier followed by an instance name
    # followed by `(`" to INSTANCE_RE but are NOT module instances. Expanded
    # beyond the original 7-keyword set because INSTANCE_RE now accepts any
    # identifier as the instance name (previously: only `u_*` was matched).
    _RESERVED = {
        # ports / nets
        "input", "output", "inout", "logic", "wire", "reg", "tri", "supply0", "supply1",
        # types
        "bit", "byte", "shortint", "int", "integer", "longint", "real", "shortreal",
        "string", "void", "var",
        # control flow
        "if", "else", "for", "foreach", "while", "do", "repeat", "forever",
        "case", "casex", "casez", "endcase",
        # blocks
        "begin", "end", "fork", "join", "join_any", "join_none",
        # processes
        "initial", "final", "always", "always_ff", "always_comb", "always_latch",
        # design constructs
        "module", "endmodule", "interface", "endinterface",
        "package", "endpackage", "program", "endprogram",
        "function", "endfunction", "task", "endtask",
        "generate", "endgenerate", "genvar",
        # declarations
        "assign", "parameter", "localparam", "typedef", "enum", "struct", "union",
        "import", "export", "extern",
        # assertions / properties
        "assert", "assume", "cover", "property", "endproperty",
        "sequence", "endsequence",
        # misc
        "return", "break", "continue", "default",
    }
    instances = [
        {"name": m.group(2), "module": m.group(1)}
        for m in INSTANCE_RE.finditer(text)
        if m.group(1) not in _RESERVED
    ]
    enums = {m.group("type"): [s.split("=")[0].strip()
                               for s in m.group("body").split(",")
                               if s.strip()]
             for m in ENUM_RE.finditer(text)}
    fsm_candidates = []
    for sr in STATE_REG_RE.finditer(text):
        states = enums.get(sr.group("type"))
        if states:
            fsm_candidates.append({
                "state_register": sr.group("name"),
                "type_name": sr.group("type"),
                "states": states,
            })
    return {
        "module_name": module_name,
        "file": str(rtl_path),
        "parameters": params,
        "ports": ports,
        "instances": instances,
        "fsm_candidates": fsm_candidates,
        "clock_domains": sorted(domains),
        "convention_violations": _check_violations(ports),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Extract RTL module structure via Verible.")
    p.add_argument("--rtl", required=True, help="Path to <module>.sv")
    p.add_argument("--syn-report", help="Optional path to syn/synth_report.txt")
    p.add_argument("--out", help="Output JSON path (default: stdout)")
    args = p.parse_args()

    verible = find_verible()
    if verible is None:
        print(f"error: {VERIBLE_BIN} not found on PATH; install verible or use rtl-explorer fallback",
              file=sys.stderr)
        return 2

    cst = _verible_json(verible, args.rtl)
    if "_error" in cst:
        print(f"error: SV parse/syntax failure:\n{cst['_error']}", file=sys.stderr)
        return 3
    payload = _parse_text(Path(args.rtl))
    if args.syn_report:
        payload["synth_summary"] = _parse_synth_report(Path(args.syn_report))
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
