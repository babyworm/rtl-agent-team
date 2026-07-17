#!/usr/bin/env python3
"""parse_coverage.py — deterministic coverage report parser for rtl-p5s-coverage-analyze.

Parses the coverage artifacts that the rtl-p5s-func-verify pipeline actually
produces (`scripts/merge_coverage.sh`):

  - lcov `.info` tracefiles (``verilator_coverage --write-info`` output, e.g.
    ``sim/coverage/merged.info``): DA (line) and BRDA (branch) records.
  - raw Verilator ``coverage.dat`` databases (``# SystemC::Coverage-3`` keyed
    ``C '<key>' <count>`` entries): v_line, v_branch, v_toggle, and v_user
    coverage points.

Emits a deterministic JSON document (no timestamps) with per-file and
per-metric coverage percentages, a ranked uncovered-bin list, and an overall
PASS/FAIL summary judged against the project coverage targets
(references/coverage-conventions.md: 90% line, 80% toggle, 70% FSM).

Metric mapping notes (documented, never fabricated):
  - Verilator has no native FSM coverage point type; ``v_user`` coverage
    points (SVA cover / covergroup emulation, conventionally used for FSM
    state/transition coverage in this pipeline) are counted as the ``fsm``
    metric.
  - lcov tracefiles carry line/branch data only, so ``toggle`` and ``fsm``
    report ``verdict: "N/A"`` with null percentages — missing data is never
    invented.
  - ``branch`` has no default project target; its verdict stays ``N/A``
    unless ``--target-branch`` is given.

Uncovered bins are ranked deterministically by (metric priority, file, line,
detail) with priority fsm > branch > line > toggle — a static proxy for the
gap-prioritization heuristics in rtl-p5s-coverage-policy. The interpretive
high-value vs unreachable classification remains the coverage-analyst agent's
job per the skill's Responsibility_Boundary.

Usage:
    python3 parse_coverage.py sim/coverage/merged.info \
        [-o coverage_summary.json] [--format auto|lcov|dat] \
        [--target-line 90] [--target-toggle 80] [--target-fsm 70] \
        [--target-branch PCT] [--min-count 1] [--max-uncovered 50]

Exit codes: 0 = overall PASS or N/A, 1 = overall FAIL, 2 = usage/parse error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

METRICS = ("line", "toggle", "fsm", "branch")
# Deterministic ranking proxy: FSM and branch gaps are usually the most
# architecturally significant; toggle gaps the least.
RANK_PRIORITY = {"fsm": 0, "branch": 1, "line": 2, "toggle": 3}

DAT_HEADER_RE = re.compile(r"^# SystemC::Coverage")
DAT_ENTRY_RE = re.compile(r"^C '(.*)' (\d+)\s*$")
# Verilator page field prefix → metric name.
DAT_PAGE_METRIC = {
    "v_line": "line",
    "v_branch": "branch",
    "v_toggle": "toggle",
    "v_user": "fsm",  # user points = SVA cover/covergroup, used for FSM here
}

LCOV_DA_RE = re.compile(r"^DA:(\d+),(\d+)")
LCOV_BRDA_RE = re.compile(r"^BRDA:(\d+),(\d+),(\d+),(-|\d+)")
LCOV_SF_RE = re.compile(r"^SF:(.+)$")


class CoverageParseError(Exception):
    """Raised when the coverage input cannot be parsed."""


def detect_format(path, text):
    """Return 'dat' or 'lcov' from content first, extension second."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if DAT_HEADER_RE.match(stripped) or DAT_ENTRY_RE.match(stripped):
            return "dat"
        if stripped.startswith(("TN:", "SF:", "DA:", "BRDA:")):
            return "lcov"
        break
    suffix = Path(path).suffix.lower()
    if suffix == ".dat":
        return "dat"
    if suffix == ".info":
        return "lcov"
    raise CoverageParseError(
        f"{path}: cannot auto-detect format (expected lcov .info records or "
        "a '# SystemC::Coverage' .dat header) — pass --format explicitly")


def parse_lcov(path, text):
    """Parse an lcov tracefile into coverage points.

    Returns [{metric, file, line, count, detail}]. Only DA (line) and
    BRDA (branch) records are consumed; LF/LH/BRF/BRH are recomputed.
    """
    points = []
    current_file = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("TN:") or line == "end_of_record":
            if line == "end_of_record":
                current_file = None
            continue
        m = LCOV_SF_RE.match(line)
        if m:
            current_file = m.group(1).strip()
            continue
        m = LCOV_DA_RE.match(line)
        if m:
            if current_file is None:
                raise CoverageParseError(
                    f"{path}:{lineno}: DA record before any SF record")
            points.append({"metric": "line", "file": current_file,
                           "line": int(m.group(1)), "count": int(m.group(2)),
                           "detail": ""})
            continue
        m = LCOV_BRDA_RE.match(line)
        if m:
            if current_file is None:
                raise CoverageParseError(
                    f"{path}:{lineno}: BRDA record before any SF record")
            taken = 0 if m.group(4) == "-" else int(m.group(4))
            points.append({"metric": "branch", "file": current_file,
                           "line": int(m.group(1)), "count": taken,
                           "detail": f"block {m.group(2)} branch {m.group(3)}"})
            continue
        # FN/FNDA/LF/LH/BRF/BRH and unknown records are ignored.
    return points


def parse_dat_key(key):
    """Split a Verilator coverage key into its \\x01<k>\\x02<v> fields."""
    fields = {}
    for segment in key.split("\x01"):
        if not segment:
            continue
        if "\x02" not in segment:
            continue
        k, v = segment.split("\x02", 1)
        fields[k] = v
    return fields


def parse_dat(path, text):
    """Parse a raw Verilator coverage.dat into coverage points."""
    points = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = DAT_ENTRY_RE.match(line.strip())
        if not m:
            raise CoverageParseError(
                f"{path}:{lineno}: unrecognized coverage.dat entry: {line!r}")
        fields = parse_dat_key(m.group(1))
        count = int(m.group(2))
        page = fields.get("page", "")
        prefix = page.split("/", 1)[0]
        metric = DAT_PAGE_METRIC.get(prefix)
        if metric is None:
            # Unknown point type: skip rather than mis-categorize.
            continue
        detail = fields.get("o", "")
        hier = fields.get("h", "")
        if hier:
            detail = f"{detail} @ {hier}" if detail else f"@ {hier}"
        points.append({"metric": metric,
                       "file": fields.get("f", "<unknown>"),
                       "line": int(fields.get("l", 0)),
                       "count": count,
                       "detail": detail})
    return points


def summarize_metric(points, min_count):
    """Return (covered, total, pct) for a list of points."""
    total = len(points)
    covered = sum(1 for p in points if p["count"] >= min_count)
    pct = round(100.0 * covered / total, 2) if total else None
    return covered, total, pct


def build_report(points, source, fmt, targets, min_count, max_uncovered):
    """Assemble the deterministic JSON document."""
    by_metric = {metric: [p for p in points if p["metric"] == metric]
                 for metric in METRICS}

    summary_metrics = {}
    verdicts = []
    for metric in METRICS:
        covered, total, pct = summarize_metric(by_metric[metric], min_count)
        target = targets[metric]
        if total == 0 or target is None:
            verdict = "N/A"
        else:
            verdict = "PASS" if pct >= target else "FAIL"
        verdicts.append(verdict)
        summary_metrics[metric] = {
            "covered": covered, "total": total, "pct": pct,
            "target_pct": target, "verdict": verdict,
        }

    if "FAIL" in verdicts:
        overall = "FAIL"
    elif "PASS" in verdicts:
        overall = "PASS"
    else:
        overall = "N/A"

    file_names = sorted({p["file"] for p in points})
    files = []
    for fname in file_names:
        entry = {"file": fname, "metrics": {}}
        for metric in METRICS:
            fpoints = [p for p in by_metric[metric] if p["file"] == fname]
            covered, total, pct = summarize_metric(fpoints, min_count)
            entry["metrics"][metric] = {"covered": covered, "total": total,
                                        "pct": pct}
        files.append(entry)

    uncovered_all = sorted(
        (p for p in points if p["count"] < min_count),
        key=lambda p: (RANK_PRIORITY[p["metric"]], p["file"], p["line"],
                       p["detail"]))
    uncovered = [
        {"rank": i, "metric": p["metric"], "file": p["file"],
         "line": p["line"], "detail": p["detail"], "count": p["count"]}
        for i, p in enumerate(uncovered_all[:max_uncovered], 1)
    ]

    return {
        "tool": "parse_coverage.py",
        "input": source,
        "format": fmt,
        "min_count": min_count,
        "summary": {
            "overall_verdict": overall,
            "metrics": summary_metrics,
            "uncovered_total": len(uncovered_all),
            "files_total": len(file_names),
        },
        "files": files,
        "uncovered": uncovered,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Parse Verilator/lcov coverage data into a deterministic "
                    "JSON summary (per-file/per-metric coverage %%, ranked "
                    "uncovered bins, PASS/FAIL vs project targets).",
        epilog="Limitations: lcov .info carries only line (DA) and branch "
               "(BRDA) data, so toggle/fsm are N/A there; in .dat inputs, "
               "v_user coverage points are counted as the fsm metric "
               "(Verilator has no native FSM point type); branch has no "
               "default target (verdict N/A unless --target-branch is set). "
               "Reachability classification (high-value vs unreachable) is "
               "NOT done here — it stays with the coverage-analyst agent.")
    parser.add_argument("input",
                        help="coverage input: lcov .info (merge_coverage.sh "
                             "output) or raw Verilator coverage.dat")
    parser.add_argument("-o", "--output",
                        help="output JSON path (default: stdout)")
    parser.add_argument("--format", choices=("auto", "lcov", "dat"),
                        default="auto",
                        help="input format (default: auto-detect from "
                             "content, then extension)")
    parser.add_argument("--target-line", type=float, default=90.0,
                        help="line coverage target %% (default: 90)")
    parser.add_argument("--target-toggle", type=float, default=80.0,
                        help="toggle coverage target %% (default: 80)")
    parser.add_argument("--target-fsm", type=float, default=70.0,
                        help="FSM coverage target %% (default: 70)")
    parser.add_argument("--target-branch", type=float, default=None,
                        help="branch coverage target %% (default: none — "
                             "branch is informational, verdict N/A)")
    parser.add_argument("--min-count", type=int, default=1,
                        help="hits required for a bin to count as covered "
                             "(default: 1)")
    parser.add_argument("--max-uncovered", type=int, default=50,
                        help="cap on ranked uncovered bins listed in the "
                             "JSON (default: 50; total always reported)")
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.is_file():
        print(f"ERROR: coverage input not found: {src} — run "
              "/rtl-agent-team:rtl-p5s-func-verify first; do not fabricate "
              "coverage numbers.", file=sys.stderr)
        return 2

    text = src.read_text(errors="replace")
    try:
        fmt = args.format if args.format != "auto" else detect_format(src, text)
        points = parse_lcov(src, text) if fmt == "lcov" else parse_dat(src, text)
    except CoverageParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not points:
        print(f"ERROR: {src}: no coverage records found "
              f"(parsed as {fmt}) — refusing to emit an empty report.",
              file=sys.stderr)
        return 2

    targets = {"line": args.target_line, "toggle": args.target_toggle,
               "fsm": args.target_fsm, "branch": args.target_branch}
    report = build_report(points, args.input, fmt, targets,
                          args.min_count, args.max_uncovered)

    payload = json.dumps(report, indent=2) + "\n"
    overall = report["summary"]["overall_verdict"]
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        print(f"Wrote {out}: overall_verdict={overall} "
              f"uncovered={report['summary']['uncovered_total']}")
    else:
        sys.stdout.write(payload)
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
