#!/usr/bin/env python3
"""Check a verification-point plan against the selected simulator runs."""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from merge_coverpoint_logs import BIN, END
from verify_evidence import (CHECK_POINT, HDL_SUFFIXES, POINT_PLAN, assess_records, check_point_error, digest,
                             failed_case_labels, has_implicit_top, point_fingerprint, runtime_state_root,
                             seed_log_sizes, source_matches)


TOKEN = r"[A-Za-z0-9_.:\[\]-]+"
KINDS = ("coverpoint", "assertion", "scoreboard")


def json_object(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def read_plan(root):
    rows = json_object(root / POINT_PLAN).get("points")
    if not isinstance(rows, list) or not rows:
        raise ValueError("points must be a nonempty list")
    plan = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each point must be an object")
        name = row.get("id")
        if not isinstance(name, str) or not re.fullmatch(TOKEN, name) or name in plan:
            raise ValueError(f"invalid or duplicate point ID: {name!r}")
        if row.get("kind") not in KINDS or row.get("confidence") not in ("high", "low"):
            raise ValueError(f"{name}: invalid kind or confidence")
        fields = ["requirement", "source", "trigger", "expected_result", "basis"]
        if row["confidence"] == "low":
            fields.append("resolution")
        for field in fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{name}: missing {field}")
        minimum = row.get("minimum_hits", 1)
        if type(minimum) is not int or minimum < 1:
            raise ValueError(f"{name}: minimum_hits must be a positive integer")
        plan[name] = row
    return plan


def check_p3_criteria(root, plan):
    path = root / "docs/phase-3-uarch/iron-requirements.json"
    if not path.exists():
        return
    requirements = json.loads(path.read_text())
    if isinstance(requirements, dict):
        requirements = requirements.get("requirements", requirements.get("iron_requirements"))
    if not isinstance(requirements, list):
        raise ValueError(f"{path}: expected a requirements list")
    kinds_by_ac = defaultdict(set)
    for point in plan.values():
        kinds_by_ac[point["requirement"]].add(point["kind"])
    gaps = []
    for req in requirements:
        criteria = req.get("acceptance_criteria", []) if isinstance(req, dict) else []
        if not isinstance(criteria, list):
            continue
        for ac in criteria:
            if not isinstance(ac, dict) or ac.get("verifiable") is False:
                continue
            method = ac.get("test_method")
            if method not in ("assertion", "cocotb", "coverpoint"):
                continue
            ac_id = ac.get("ac_id")
            if not isinstance(ac_id, str) or not ac_id.strip():
                raise ValueError(f"{req.get('id', '?')}: {method} criterion lacks an ac_id")
            kinds = kinds_by_ac[ac_id]
            if not kinds:
                gaps.append(f"{ac_id}: no linked simulation point")
            elif method == "coverpoint" and "coverpoint" not in kinds:
                gaps.append(f"{ac_id}: missing coverpoint for the specified event")
            elif method != "coverpoint" and not kinds.intersection(("assertion", "scoreboard")):
                gaps.append(f"{ac_id}: missing assertion or scoreboard")
    if gaps:
        raise ValueError(", ".join(gaps))


def runtime_evidence(root):
    selected = json_object(root / "docs/phase-5-verify/judgment.json").get("simulation_runs")
    if (not isinstance(selected, list) or not selected
            or not all(isinstance(key, str) and key.strip() for key in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("simulation_runs must list distinct run IDs")
    runs = json_object(runtime_state_root(root) / "state/verify-evidence.json").get("runs")
    if not isinstance(runs, list):
        raise ValueError("missing runner evidence index")
    records = {}
    for record in runs:
        if isinstance(record, dict) and record.get("run_id") in selected:
            key = record["run_id"]
            if key in records:
                raise ValueError(f"ambiguous runner evidence for {key}")
            records[key] = record
    @lru_cache(maxsize=None)
    def current_digest(path):
        return digest(path) if path.is_file() else None

    paths = set()
    selected_hdl = set()
    for key in selected:
        record = records.get(key, {})
        if record.get("verdict") != "PASS" or record.get("compile_only"):
            raise ValueError(f"{key}: missing passing simulation")
        if has_implicit_top(record):
            raise ValueError(f"{key}: rerun simulation with an explicitly selected top")
        sources = record.get("sources")
        identity = record.get("source_identity") if isinstance(record.get("source_identity"), dict) else {}
        if not isinstance(sources, dict) or not sources or not all(
            isinstance(expected, str) and source_matches(root / name, expected, identity.get(name))
            for name, expected in sources.items()
        ):
            raise ValueError(f"{key}: missing or changed simulation sources")
        selected_hdl.update(name for name in sources if Path(name).suffix in HDL_SUFFIXES)
        logs = [(record.get("log"), record.get("log_sha256"))]
        if "runtime_log" in record:
            runtime = record["runtime_log"]
            if not isinstance(runtime, dict):
                raise ValueError(f"{key}: invalid runtime_log")
            logs.append((runtime.get("path"), runtime.get("sha256")))
        for name, expected in logs:
            if not isinstance(name, str) or not name:
                raise ValueError(f"{key}: missing simulation log path")
            log = (root / name).resolve()
            if not isinstance(expected, str) or current_digest(log) != expected:
                raise ValueError(f"{key}: missing or changed log {name}")
        if log in paths:
            raise ValueError(f"{key}: simulation log selected more than once")
        paths.add(log)
        fingerprints = record.get("point_fingerprints", {})
        if not isinstance(fingerprints, dict):
            raise ValueError(f"{key}: invalid point_fingerprints")
        yield log, fingerprints, recorded_seed_sizes(log, expected, record)
    _, _, failures = assess_records(selected_hdl, runs)
    if failures:
        raise ValueError(f"unresolved failing simulations: {failed_case_labels(failures)}")


def recorded_seed_sizes(log, expected_digest, record):
    length = log.stat().st_size
    if "seed_log_sizes" in record:
        sizes = record["seed_log_sizes"]
        if (not isinstance(sizes, list) or not sizes or
                not all(type(size) is int and size > 0 for size in sizes) or sum(sizes) != length):
            raise ValueError(f"{log}: seed boundaries do not match runtime evidence")
        return sizes

    # Older campaigns stored a raw concatenation. Recover its boundaries only
    # when the original seed files reproduce the recorded stream byte for byte.
    context = record.get("context", "")
    if log.name == "runtime.log" and context.startswith("uvm:"):
        files = list(log.parent.glob("seed_*/sim.log"))
    elif log.name == "campaign.log" and context.startswith("cocotb Makefile;"):
        files = list(log.parent.glob("seed_*.log"))
    else:
        return [length]
    if len(files) > 1:
        for order in dict.fromkeys((tuple(sorted(files)), tuple(files))):
            try:
                return seed_log_sizes([str(path) for path in order], expected_digest)
            except (OSError, ValueError):
                continue
    return [length]


def count_seed(stream, size, path, plan, counts):
    bins = set()
    checked = set()
    coverage_complete = False
    while size:
        raw = stream.readline(size)
        if not raw:
            raise ValueError(f"{path}: truncated seed log")
        size -= len(raw)
        line = raw.decode("utf-8", errors="replace").strip().removeprefix("# ")
        if line.startswith("RAT_COV_BIN"):
            match = BIN.fullmatch(line)
            if not match or coverage_complete or match[1] in bins:
                raise ValueError(f"{path}: malformed or repeated bin without a verified seed boundary: {line}")
            name, hits, _ = match.groups()
            bins.add(name)
            if name in plan:
                if plan[name]["kind"] != "coverpoint":
                    raise ValueError(f"{name}: bin kind differs from plan")
                counts[name] += int(hits)
        elif line.startswith("RAT_COV_END"):
            match = END.fullmatch(line)
            if not match or coverage_complete or int(match[1]) != len(bins):
                raise ValueError(f"{path}: incomplete or repeated coverage snapshot within a seed")
            coverage_complete = True
        elif line.startswith("RAT_CHECK_POINT"):
            error = check_point_error(line)
            if error:
                raise ValueError(f"{path}: {error}")
            name, completed, _ = CHECK_POINT.fullmatch(line).groups()
            if name in plan:
                if plan[name]["kind"] == "coverpoint":
                    raise ValueError(f"{name}: check kind differs from plan")
                if name in checked:
                    raise ValueError(f"{name}: repeated check summary without a verified seed boundary")
                checked.add(name)
                counts[name] += int(completed)
    if bins and not coverage_complete:
        raise ValueError(f"{path}: missing RAT_COV_END")


def simulation_point_checks(root, plan_only=False):
    label = "simulation point plan"
    try:
        root = Path(root).resolve()
        plan = read_plan(root)
        check_p3_criteria(root, plan)
        input_hashes = {}
        fingerprints = {name: point_fingerprint(root, point, input_hashes) for name, point in plan.items()}
        if plan_only:
            return [{"check": label, "passed": True, "reason": f"{len(plan)} points"}]
        label = "simulation point evidence"
        counts = Counter()
        for log, recorded, sizes in runtime_evidence(root):
            current = {name: plan[name] for name in plan if recorded.get(name) == fingerprints[name]}
            with log.open("rb") as stream:
                for size in sizes:
                    count_seed(stream, size, log, current, counts)
        checks = []
        for name, point in plan.items():
            minimum = point.get("minimum_hits", 1)
            if name not in counts:
                reason = "no matching runtime record for the current point"
            elif point["kind"] == "coverpoint":
                reason = f"{counts[name]}/{minimum} hits"
            else:
                reason = f"{counts[name]}/{minimum} completed, 0 failures"
            checks.append({"check": f"simulation point {name}", "reason": reason,
                           "passed": counts[name] >= minimum})
        if all(point["kind"] == "coverpoint" for point in plan.values()):
            checks.append({"check": "functional simulation outcome", "passed": False,
                           "reason": "plan an assertion or scoreboard to check the observed behavior"})
        return checks
    except (OSError, ValueError, RuntimeError) as exc:
        return [{"check": label, "passed": False, "reason": str(exc)}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    checks = simulation_point_checks(args.root, args.plan_only)
    passed = all(check["passed"] for check in checks)
    print(json.dumps({"verdict": "PASS" if passed else "FAIL", "checks": checks}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
