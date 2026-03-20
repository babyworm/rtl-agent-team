#!/usr/bin/env python3
"""vcd_diff.py — Cycle-by-cycle VCD signal comparison.

Compares two VCD files (expected vs actual) and reports the first divergence
point with surrounding context. Useful for bug reproduction verification.

Usage:
    python3 vcd_diff.py expected.vcd actual.vcd [--signals sig1,sig2]

Output:
    - First divergence cycle and signal name
    - Context window (N cycles before/after divergence)
    - Summary: total signals compared, match/mismatch count
"""

import argparse
import re
import sys
from collections import defaultdict


def parse_vcd_signals(filepath, filter_signals=None):
    """Parse VCD file into {signal_name: [(time, value), ...]} dict."""
    signals = {}       # id -> name
    values = defaultdict(list)  # id -> [(time, value)]
    current_time = 0

    with open(filepath) as f:
        in_defs = True
        scope_stack = []

        for line in f:
            line = line.strip()

            if line == "$end":
                continue

            if in_defs:
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 3:
                        scope_stack.append(parts[2])
                elif line.startswith("$upscope"):
                    if scope_stack:
                        scope_stack.pop()
                elif line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 5:
                        var_id = parts[3]
                        var_name = parts[4]
                        full_name = ".".join(scope_stack + [var_name])
                        if filter_signals is None or var_name in filter_signals or full_name in filter_signals:
                            signals[var_id] = full_name
                elif line.startswith("$enddefinitions"):
                    in_defs = False
            else:
                # Timestamp
                m = re.match(r"^#(\d+)", line)
                if m:
                    current_time = int(m.group(1))
                    continue

                # Scalar value change: 0/1/x/z followed by signal id
                m = re.match(r"^([01xXzZ])(.+)$", line)
                if m:
                    val, sig_id = m.group(1), m.group(2)
                    if sig_id in signals:
                        values[sig_id].append((current_time, val))
                    continue

                # Vector value change: b<bits> <id>
                m = re.match(r"^b([01xXzZ]+)\s+(.+)$", line)
                if m:
                    val, sig_id = m.group(1), m.group(2)
                    if sig_id in signals:
                        values[sig_id].append((current_time, val))

    # Convert to name-keyed dict
    result = {}
    for sig_id, name in signals.items():
        result[name] = values[sig_id]

    return result


def find_divergences(expected, actual):
    """Compare two signal dicts and find first divergence per signal."""
    all_signals = sorted(set(expected.keys()) & set(actual.keys()))
    only_expected = sorted(set(expected.keys()) - set(actual.keys()))
    only_actual = sorted(set(actual.keys()) - set(expected.keys()))

    divergences = []

    for sig in all_signals:
        exp_changes = dict(expected[sig])
        act_changes = dict(actual[sig])
        all_times = sorted(set(exp_changes.keys()) | set(act_changes.keys()))

        exp_val = "x"
        act_val = "x"

        for t in all_times:
            if t in exp_changes:
                exp_val = exp_changes[t]
            if t in act_changes:
                act_val = act_changes[t]

            if exp_val != act_val:
                divergences.append({
                    "signal": sig,
                    "time": t,
                    "expected": exp_val,
                    "actual": act_val,
                })
                break

    divergences.sort(key=lambda d: d["time"])
    return divergences, all_signals, only_expected, only_actual


def main():
    parser = argparse.ArgumentParser(description="VCD cycle-by-cycle comparison")
    parser.add_argument("expected", help="Expected (golden) VCD file")
    parser.add_argument("actual", help="Actual (DUT) VCD file")
    parser.add_argument("--signals", help="Comma-separated signal filter", default=None)
    args = parser.parse_args()

    filter_sigs = set(args.signals.split(",")) if args.signals else None

    print(f"Comparing: {args.expected} vs {args.actual}")
    exp = parse_vcd_signals(args.expected, filter_sigs)
    act = parse_vcd_signals(args.actual, filter_sigs)

    divs, common, only_exp, only_act = find_divergences(exp, act)

    # Report
    print(f"\nSignals compared: {len(common)}")
    if only_exp:
        print(f"Only in expected: {', '.join(only_exp)}")
    if only_act:
        print(f"Only in actual:   {', '.join(only_act)}")

    if not divs:
        print("\nRESULT: MATCH — no divergences found")
        return 0

    print(f"\nRESULT: MISMATCH — {len(divs)} signal(s) diverge")
    print(f"\nFirst divergence at time {divs[0]['time']}:")
    print(f"  Signal:   {divs[0]['signal']}")
    print(f"  Expected: {divs[0]['expected']}")
    print(f"  Actual:   {divs[0]['actual']}")

    if len(divs) > 1:
        print(f"\nAll divergences (first per signal):")
        for d in divs:
            print(f"  t={d['time']:>8}  {d['signal']:<40}  exp={d['expected']:<10}  act={d['actual']}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
