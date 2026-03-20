#!/usr/bin/env python3
"""compare_3way.py — 3-way consistency check: refC vs BFM vs RTL.

Compares output files from three models on shared test vectors.
Reports pairwise matches and identifies first divergence per signal.

Usage:
    python3 compare_3way.py \
        --refc   refc/build/output.bin \
        --bfm    bfm/output.bin \
        --rtl    sim/output.bin \
        [--format hex|bin|csv] \
        [--tolerance 0]

Output:
    - Pairwise comparison matrix (refC↔BFM, refC↔RTL, BFM↔RTL)
    - First divergence location per pair
    - Overall consistency verdict
"""

import argparse
import sys


def read_data(filepath, fmt):
    """Read output data from file in specified format."""
    data = []
    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                if fmt == "hex":
                    data.append(int(line, 16))
                elif fmt == "bin":
                    data.append(int(line, 2))
                else:  # csv
                    data.extend(int(v.strip(), 0) for v in line.split(",") if v.strip())
            except ValueError as e:
                print(f"WARNING: {filepath}:{line_num}: parse error: {e}", file=sys.stderr)
    return data


def compare_pair(name_a, data_a, name_b, data_b, tolerance=0):
    """Compare two data sequences, return match info."""
    min_len = min(len(data_a), len(data_b))
    mismatches = []

    for i in range(min_len):
        diff = abs(data_a[i] - data_b[i])
        if diff > tolerance:
            mismatches.append({
                "index": i,
                "val_a": data_a[i],
                "val_b": data_b[i],
                "diff": diff,
            })

    len_match = len(data_a) == len(data_b)
    return {
        "pair": f"{name_a} ↔ {name_b}",
        "len_a": len(data_a),
        "len_b": len(data_b),
        "len_match": len_match,
        "compared": min_len,
        "match_count": min_len - len(mismatches),
        "mismatch_count": len(mismatches),
        "first_mismatch": mismatches[0] if mismatches else None,
        "match": len(mismatches) == 0 and len_match,
    }


def main():
    parser = argparse.ArgumentParser(description="3-way model consistency check")
    parser.add_argument("--refc", required=True, help="RefC output file")
    parser.add_argument("--bfm", required=True, help="BFM output file")
    parser.add_argument("--rtl", required=True, help="RTL simulation output file")
    parser.add_argument("--format", choices=["hex", "bin", "csv"], default="hex")
    parser.add_argument("--tolerance", type=int, default=0, help="Allowed difference (0=bitexact)")
    args = parser.parse_args()

    refc = read_data(args.refc, args.format)
    bfm = read_data(args.bfm, args.format)
    rtl = read_data(args.rtl, args.format)

    print(f"Data lengths: refC={len(refc)}, BFM={len(bfm)}, RTL={len(rtl)}")
    print(f"Tolerance: {args.tolerance}")
    print()

    pairs = [
        compare_pair("refC", refc, "BFM", bfm, args.tolerance),
        compare_pair("refC", refc, "RTL", rtl, args.tolerance),
        compare_pair("BFM", bfm, "RTL", rtl, args.tolerance),
    ]

    # Summary table
    print(f"{'Pair':<20} {'Compared':>10} {'Match':>10} {'Mismatch':>10} {'Verdict':>10}")
    print("-" * 62)
    for p in pairs:
        verdict = "MATCH" if p["match"] else "MISMATCH"
        print(f"{p['pair']:<20} {p['compared']:>10} {p['match_count']:>10} {p['mismatch_count']:>10} {verdict:>10}")

    # First divergences
    for p in pairs:
        if p["first_mismatch"]:
            m = p["first_mismatch"]
            print(f"\n{p['pair']} first divergence at index {m['index']}:")
            print(f"  val_a=0x{m['val_a']:08x}  val_b=0x{m['val_b']:08x}  diff={m['diff']}")

    # Overall verdict
    all_match = all(p["match"] for p in pairs)
    print(f"\nOVERALL: {'CONSISTENT' if all_match else 'INCONSISTENT'}")
    return 0 if all_match else 1


if __name__ == "__main__":
    sys.exit(main())
