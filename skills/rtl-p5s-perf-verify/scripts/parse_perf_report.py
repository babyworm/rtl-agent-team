#!/usr/bin/env python3
"""parse_perf_report.py — parse performance simulation output vs BFM baseline.

Reads the performance summary block printed by the perf-monitor harness
(templates/perf-monitor-template.sv `print_summary()` task) from a simulation
run log, compares measured metrics against the BFM baseline
(`bfm/perf_baseline.json`, schema per skills/bfm-develop/references/
bfm-conventions.md), and emits the `{module}_perf.json` document defined in
references/perf-verify-conventions.md.

Expected log block (one per module):

    === Performance Summary: cabac_encoder ===
      Transactions:    3000
      Latency (min):   10 cycles
      Latency (max):   18 cycles
      Latency (avg):   12.0 cycles
      Throughput:      30.0% (3000/10000 cycles)
      Backpressure:    2.1% (210 cycles)
      Stall/bubble:    840 cycles

Metric mapping:
  - latency_cycles    = Latency (avg)            vs baseline block `clock_cycles`
                                                   (alias: `latency_cycles`)
  - stall_cycles_pct  = stall / total * 100       vs baseline block `stall_cycles_pct`
  - throughput_mbps   = out-handshake ratio * clock_mhz * bits_per_txn
                                                   vs baseline block `throughput_mbps`
    (requires --clock-mhz and --bits-per-txn; otherwise verdict N/A — never
     fabricated)

Verdict: FAIL when |delta| > threshold (default 10%, per conventions).
Exit codes: 0 = overall PASS or N/A, 1 = overall FAIL, 2 = usage/parse error.

Usage:
    python3 parse_perf_report.py --log sim/cabac_encoder/cabac_encoder_perf_run.log \
        --baseline bfm/perf_baseline.json --clock-mhz 200 --bits-per-txn 8 \
        [-o sim/cabac_encoder/cabac_encoder_perf.json] [--module cabac_encoder] \
        [--threshold-pct 10]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SUMMARY_HEADER_RE = re.compile(r"^=== Performance Summary: (\S+) ===\s*$")
FIELD_RES = {
    "transactions": re.compile(r"Transactions:\s+(\d+)"),
    "latency_avg": re.compile(r"Latency \(avg\):\s+([\d.]+) cycles"),
    "throughput": re.compile(r"Throughput:\s+([\d.]+)%\s+\((\d+)/(\d+) cycles\)"),
    "stall": re.compile(r"Stall/bubble:\s+(\d+) cycles"),
}


def parse_log(log_path, module=None):
    """Extract the perf summary block for `module` (or the first block)."""
    blocks = {}
    current = None
    for line in Path(log_path).read_text().splitlines():
        m = SUMMARY_HEADER_RE.match(line.strip())
        if m:
            current = m.group(1)
            blocks.setdefault(current, {})
            continue
        if current is None:
            continue
        for key, rx in FIELD_RES.items():
            m = rx.search(line)
            if m:
                blocks[current][key] = m.groups()
    if not blocks:
        raise ValueError(f"{log_path}: no '=== Performance Summary: ... ===' block found")
    if module:
        if module not in blocks:
            raise ValueError(
                f"{log_path}: no summary block for module '{module}' "
                f"(found: {', '.join(blocks)})")
        name = module
    else:
        name = next(iter(blocks))
    raw = blocks[name]
    missing = [k for k in FIELD_RES if k not in raw]
    if missing:
        raise ValueError(
            f"{log_path}: summary block '{name}' missing fields: {missing}")

    throughput_pct = float(raw["throughput"][0])
    total_cycles = int(raw["throughput"][2])
    stall_cycles = int(raw["stall"][0])
    if total_cycles == 0:
        raise ValueError(f"{log_path}: total cycle count is zero")
    return {
        "module": name,
        "transactions": int(raw["transactions"][0]),
        "latency_avg_cycles": float(raw["latency_avg"][0]),
        "throughput_pct": throughput_pct,
        "throughput_cycles": int(raw["throughput"][1]),
        "total_cycles": total_cycles,
        "stall_cycles": stall_cycles,
        "stall_cycles_pct": round(100.0 * stall_cycles / total_cycles, 2),
    }


def load_baseline_block(baseline_path, module):
    """Return the baseline block matching `module` from perf_baseline.json."""
    try:
        baseline = json.loads(Path(baseline_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read baseline {baseline_path}: {exc}") from exc
    blocks = baseline.get("blocks", [])
    for block in blocks:
        if block.get("name") == module:
            return block
    for block in blocks:  # tolerate case drift between BFM and RTL naming
        if str(block.get("name", "")).lower() == module.lower():
            return block
    return None


def make_metric(measured, expected, threshold_pct, notes):
    """Build one metric entry per the conventions schema."""
    if measured is None or expected is None:
        return {"measured": measured, "expected": expected,
                "delta_pct": None, "verdict": "N/A"}
    if expected == 0:
        if measured == 0:
            return {"measured": measured, "expected": expected,
                    "delta_pct": 0.0, "verdict": "PASS"}
        notes.append("expected value is 0 with nonzero measurement — FAIL")
        return {"measured": measured, "expected": expected,
                "delta_pct": None, "verdict": "FAIL"}
    delta_pct = round(100.0 * (measured - expected) / expected, 2)
    verdict = "PASS" if abs(delta_pct) <= threshold_pct else "FAIL"
    return {"measured": measured, "expected": expected,
            "delta_pct": delta_pct, "verdict": verdict}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Parse perf simulation log and compare against the BFM "
                    "baseline (10%% deviation threshold).")
    parser.add_argument("--log", required=True,
                        help="simulation run log containing the perf summary block")
    parser.add_argument("--baseline", required=True,
                        help="BFM baseline JSON (bfm/perf_baseline.json)")
    parser.add_argument("--module",
                        help="module name (default: first summary block in log)")
    parser.add_argument("--clock-mhz", type=float,
                        help="clock frequency in MHz (needed for throughput_mbps)")
    parser.add_argument("--bits-per-txn", type=float,
                        help="payload bits per output transaction (needed for "
                             "throughput_mbps)")
    parser.add_argument("--threshold-pct", type=float, default=10.0,
                        help="deviation threshold in percent (default: 10)")
    parser.add_argument("-o", "--output",
                        help="output JSON path (default: stdout)")
    args = parser.parse_args(argv)

    if not Path(args.log).is_file():
        print(f"ERROR: log file not found: {args.log}", file=sys.stderr)
        return 2
    if not Path(args.baseline).is_file():
        print(f"ERROR: baseline not found: {args.baseline} — do not fabricate "
              "baseline values; run /rtl-agent-team:bfm-develop first.",
              file=sys.stderr)
        return 2

    try:
        measured = parse_log(args.log, args.module)
        block = load_baseline_block(args.baseline, measured["module"])
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    notes = []
    if block is None:
        notes.append(f"baseline block '{measured['module']}' not found in "
                     f"{args.baseline} — all expected values N/A")
        block = {}

    throughput_measured = None
    if args.clock_mhz and args.bits_per_txn:
        throughput_measured = round(
            (measured["throughput_cycles"] / measured["total_cycles"])
            * args.clock_mhz * args.bits_per_txn, 2)
    else:
        notes.append("throughput_mbps not computed — pass --clock-mhz and "
                     "--bits-per-txn to convert handshake counts to Mbps")

    expected_latency = block.get("clock_cycles", block.get("latency_cycles"))
    metrics = {
        "throughput_mbps": make_metric(
            throughput_measured, block.get("throughput_mbps"),
            args.threshold_pct, notes),
        "latency_cycles": make_metric(
            measured["latency_avg_cycles"], expected_latency,
            args.threshold_pct, notes),
        "stall_cycles_pct": make_metric(
            measured["stall_cycles_pct"], block.get("stall_cycles_pct"),
            args.threshold_pct, notes),
    }

    verdicts = [m["verdict"] for m in metrics.values()]
    if "FAIL" in verdicts:
        overall = "FAIL"
    elif "PASS" in verdicts:
        overall = "PASS"
    else:
        overall = "N/A"
    for name, metric in metrics.items():
        if metric["verdict"] == "N/A":
            notes.append(f"{name}: verdict N/A (missing measured or expected value)")

    result = {
        "module": measured["module"],
        "run_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metrics": metrics,
        "overall_verdict": overall,
        "notes": "; ".join(notes),
    }

    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        print(f"Wrote {out}: overall_verdict={overall}")
    else:
        sys.stdout.write(payload)
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
