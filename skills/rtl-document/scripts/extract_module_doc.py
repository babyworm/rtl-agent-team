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
import shutil
import subprocess
import sys
from pathlib import Path

VERIBLE_BIN = "verible-verilog-syntax"


def find_verible() -> str | None:
    return shutil.which(VERIBLE_BIN)


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

    # Stubbed: real CST processing comes in Task 3+.
    payload = {
        "module_name": Path(args.rtl).stem,
        "file": args.rtl,
        "parameters": [],
        "ports": [],
        "instances": [],
        "fsm_candidates": [],
        "clock_domains": [],
        "convention_violations": [],
    }
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
