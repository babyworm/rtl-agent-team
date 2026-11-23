#!/usr/bin/env python3
"""
Parse Yosys 'stat' output and produce syn/summary.json.
Usage: python parse_yosys_stat.py <yosys_output.txt> [--output syn/summary.json]

Target: ASIC TSMC 28nm (NanGate45 proxy)
Area metric: NAND2-FO2 gate equivalents (NAND2X1 = 0.798 um2 in NanGate45)

Detects:
- Cell counts by type
- Inferred latches ($_DLATCH_* → HARD FAIL)
- Area (um2) from liberty-mapped stat output
- NAND2-FO2 gate count (area / 0.798)
"""

import json
import re
import sys
from pathlib import Path

# NanGate45 NAND2X1 area in um2 (TSMC 28nm proxy)
NAND2_AREA_UM2 = 0.798


def parse_stat_output(text: str) -> dict:
    """Parse Yosys stat command output."""
    result = {
        "technology": "ASIC TSMC 28nm (NanGate45 proxy)",
        "library": "NangateOpenCellLibrary_typical",
        "cells": {},
        "total_cells": 0,
        "wires": 0,
        "wire_bits": 0,
        "memories": 0,
        "memory_bits": 0,
        "latches_found": 0,
        "area_um2": None,
        "gate_count_nand2": None,
        "nand2_area_um2": NAND2_AREA_UM2,
        "concerns": [],
    }

    in_stat = False
    in_modern_stat = False
    in_modern_cells = False
    _SUMMARY_WORDS = {
        "wires", "cells", "ports", "memories", "processes", "submodules", "unknown",
    }
    for line in text.splitlines():
        line = line.strip()

        if re.fullmatch(r"=== .+ ===", line):
            in_stat = False
            in_modern_stat = True
            in_modern_cells = False

        if "Statistics" in line or "Number of cells:" in line:
            in_stat = True

        if not in_stat and not in_modern_stat:
            continue

        if not line or line.startswith("Chip area "):
            in_modern_cells = False

        if in_modern_stat:
            modern_wire_match = re.match(r'(\d+)\s+wires$', line)
            modern_wire_bits_match = re.match(r'(\d+)\s+wire bits$', line)
            modern_mem_match = re.match(r'(\d+)\s+memories$', line)
            modern_mem_bits_match = re.match(r'(\d+)\s+memory bits$', line)
            modern_total_match = re.match(r'(\d+)\s+cells$', line)
            modern_other_hdr = re.match(
                r'(\d+)\s+(?:public wires|public wire bits|ports|port bits|processes|submodules)$',
                line,
            )
            if modern_wire_match:
                result["wires"] = int(modern_wire_match.group(1))
                in_modern_cells = False
                continue
            if modern_wire_bits_match:
                result["wire_bits"] = int(modern_wire_bits_match.group(1))
                in_modern_cells = False
                continue
            if modern_mem_match:
                result["memories"] = int(modern_mem_match.group(1))
                in_modern_cells = False
                continue
            if modern_mem_bits_match:
                result["memory_bits"] = int(modern_mem_bits_match.group(1))
                in_modern_cells = False
                continue
            if modern_other_hdr:
                in_modern_cells = False
                continue
            if modern_total_match:
                result["cells"] = {}
                result["total_cells"] = int(modern_total_match.group(1))
                result["latches_found"] = 0
                result["concerns"] = []
                in_modern_cells = True
                continue

        # Cell type counts: legacy ($_DFF_P_ 42 or NAND2_X1 42) or modern (42 $_AND_ or 42 NAND2_X1)
        cell_match = (
            re.match(r'^(\$\w+|\$_\w+_?|[A-Za-z][A-Za-z0-9_]+)\s+(\d+)$', line)
            if in_stat
            else None
        )
        if cell_match and cell_match.group(1).lower() in _SUMMARY_WORDS:
            cell_match = None
        modern_cell_match = None
        if in_modern_stat:
            if in_modern_cells:
                modern_cell_match = re.match(r'^(\d+)\s+(\S+)$', line)
            else:
                modern_cell_match = re.match(r'^(\d+)\s+(\$\S+)$', line)
        if cell_match:
            cell_type = cell_match.group(1)
            count = int(cell_match.group(2))
            result["cells"][cell_type] = count
            result["total_cells"] += count
        elif modern_cell_match:
            count = int(modern_cell_match.group(1))
            cell_type = modern_cell_match.group(2)
            result["cells"][cell_type] = count
        else:
            cell_type = None
            count = 0

        if cell_type is not None:
            upper_cell = cell_type.upper()
            # Check for latches (Yosys $_DLATCH_* and liberty-mapped DLH/DLL/TLAT/LATCH cells)
            if (
                "DLATCH" in upper_cell
                or "LATCH" in upper_cell
                or re.search(r'(?:^|_)(?:DL[LH]|DLXT|TLAT)(?:[_A-Z0-9]|$)', upper_cell)
            ):
                result["latches_found"] += count
                result["concerns"].append(
                    f"CRITICAL: {count} latch(es) inferred ({cell_type})"
                )

            # Check for concerning cells
            if cell_type == "$mul":
                result["concerns"].append(
                    f"WARN: {count} multiplier(s) inferred — verify area intent"
                )
            if cell_type == "$mem":
                result["concerns"].append(
                    f"INFO: {count} memory/ies inferred — verify SRAM intent"
                )

        # Wire counts
        wire_match = re.match(r'Number of wires:\s+(\d+)', line) if in_stat else None
        if wire_match:
            result["wires"] = int(wire_match.group(1))

        wire_bits_match = (
            re.match(r'Number of wire bits:\s+(\d+)', line) if in_stat else None
        )
        if wire_bits_match:
            result["wire_bits"] = int(wire_bits_match.group(1))

        # Memory
        mem_match = re.match(r'Number of memories:\s+(\d+)', line) if in_stat else None
        if mem_match:
            result["memories"] = int(mem_match.group(1))

        # Area (from stat -liberty)
        area_match = re.match(r'Chip area for .*:\s+([\d.]+)', line)
        if area_match:
            result["area_um2"] = float(area_match.group(1))

    # Compute NAND2-FO2 gate count from area
    if result["area_um2"] is not None:
        result["gate_count_nand2"] = round(result["area_um2"] / NAND2_AREA_UM2)

    return result


def generate_verdict(result: dict) -> str:
    """Generate PASS/FAIL verdict."""
    if result["latches_found"] > 0:
        return f"FAIL: {result['latches_found']} inferred latch(es) detected"
    if result["total_cells"] == 0:
        return "FAIL: no cells synthesized (empty design or synthesis error)"
    if result["area_um2"] is None:
        return "WARN: no liberty-mapped area — ensure NanGate45 liberty was used"
    return "PASS"


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <yosys_output.txt> [--output file.json]")
        sys.exit(2)

    input_file = Path(sys.argv[1])
    output_file = Path("syn/summary.json")

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 >= len(sys.argv):
            print("ERROR: --output requires a file path", file=sys.stderr)
            sys.exit(2)
        output_file = Path(sys.argv[idx + 1])

    text = input_file.read_text()
    result = parse_stat_output(text)
    result["verdict"] = generate_verdict(result)
    result["source_file"] = str(input_file)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    print(f"Technology: {result['technology']}")
    print(f"Cells: {result['total_cells']}")
    print(f"Latches: {result['latches_found']}")
    if result["area_um2"] is not None:
        print(f"Area: {result['area_um2']:.1f} um2")
    if result["gate_count_nand2"] is not None:
        print(f"Gate count (NAND2-FO2): {result['gate_count_nand2']:,}")
    for c in result["concerns"]:
        print(f"  {c}")
    print(f"Verdict: {result['verdict']}")
    print(f"Written to: {output_file}")

    sys.exit(1 if result["verdict"].startswith("FAIL") else 0)


if __name__ == "__main__":
    main()
