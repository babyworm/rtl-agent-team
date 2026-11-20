#!/usr/bin/env python3
# rat-version: 2.0.0
"""Merge complete, matching testbench bin-count records across seed logs."""

import argparse
from pathlib import Path
import re
import sys

from verify_evidence import atomic_json


BIN = re.compile(r"RAT_COV_BIN ([A-Za-z0-9_.:\[\]-]+) ([0-9]+) ([1-9][0-9]*)")
END = re.compile(r"RAT_COV_END ([1-9][0-9]*)")


def read_bins(path):
    bins = {}
    completed = False
    with path.open(encoding="utf-8", errors="replace") as stream:
        for raw in stream:
            line = raw.strip().removeprefix("# ")
            if not line.startswith(("RAT_COV_BIN", "RAT_COV_END")):
                continue
            if completed:
                raise ValueError(f"{path}: extra records after RAT_COV_END")
            match = BIN.fullmatch(line)
            if match:
                name, hits, minimum = match.groups()
                if name in bins:
                    raise ValueError(f"{path}: duplicate bin {name}")
                bins[name] = (int(hits), int(minimum))
            else:
                match = END.fullmatch(line)
                if not match or int(match[1]) != len(bins):
                    raise ValueError(f"{path}: invalid bin record or final bin count")
                completed = True
    if not completed:
        raise ValueError(f"{path}: missing complete RAT_COV_BIN records")
    return bins


def merge(paths):
    if not paths or len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("need distinct seed logs")
    minimums = None
    totals = {}
    for path in paths:
        bins = read_bins(path)
        current = {name: minimum for name, (_, minimum) in bins.items()}
        if minimums is None:
            minimums = current
        elif current != minimums:
            raise ValueError(f"{path}: bin inventory or minimum hits differ across seeds")
        for name, (hits, _) in bins.items():
            totals[name] = totals.get(name, 0) + hits
    covered = sum(totals[name] >= minimum for name, minimum in minimums.items())
    return {
        "schema_version": 1,
        "scope": "functional_only",
        "seed_logs": list(map(str, paths)),
        "covered_bins": covered,
        "total_bins": len(minimums),
        "percent": 100 * covered / len(minimums),
        "bins": {name: {"hits": totals[name], "minimum_hits": minimum,
                        "covered": totals[name] >= minimum} for name, minimum in minimums.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("logs", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        atomic_json(args.output, merge(args.logs))
    except (OSError, ValueError) as exc:
        print(f"Coverpoint merge: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
