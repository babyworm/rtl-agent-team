#!/usr/bin/env python3
"""Compute weighted PPA delta and evaluate convergence / early-plateau.

Reads:
    - Current ppa-report.json
    - .rat/state/ppa-loop-state.json (mutated in-place)
    - requirements.json["ppa_targets"]

Writes updated state file in place and prints verdict:
    CONTINUE | CONVERGED_STREAK | CONVERGED_TARGETS | EARLY_PLATEAU | MAX_CYCLES
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile


VALID_VERDICTS = {
    "CONTINUE",
    "CONVERGED_STREAK",
    "CONVERGED_TARGETS",
    "EARLY_PLATEAU",
    "MAX_CYCLES",
    "TIMING_REGRESSION",
}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def normalize_weights(w):
    s = sum(w.values())
    if s <= 0:
        raise ValueError("weights sum must be positive")
    return {k: v / s for k, v in w.items()}


def weighted_delta(curr, prev, targets, weights, clock_hz=None):
    # Compute target_period_ns from clock_hz; fallback to a conservative default.
    if clock_hz and clock_hz > 0:
        target_period_ns = 1e9 / float(clock_hz)
    else:
        # Fallback when clock_hz is missing — use a conservative 1.0 ns period
        # (800 MHz default design target) so pre-clock_hz states still compute.
        target_period_ns = 1.0
    target_power = float(targets.get("power_mw", 100.0))
    target_area = float(targets.get("area_um2", 50000.0))
    d_timing = (curr["timing"]["wns_ns"] - prev["timing"]["wns_ns"]) / target_period_ns
    d_power = (prev["power"]["total_mw"] - curr["power"]["total_mw"]) / target_power
    d_area = (prev["area"]["total_um2"] - curr["area"]["total_um2"]) / target_area
    w = normalize_weights(weights)
    return 100.0 * (w["timing"] * d_timing + w["power"] * d_power + w["area"] * d_area)


def targets_met(report, targets):
    target_slack = float(targets.get("timing_slack_ns", 0.0))
    return {
        "timing": report["timing"]["wns_ns"] >= target_slack,
        "power": report["power"]["total_mw"] <= float(targets.get("power_mw", 1e9)),
        "area": report["area"]["total_um2"] <= float(targets.get("area_um2", 1e9)),
    }


def evaluate_convergence(state, curr_report, targets, weights, clock_hz=None):
    conv = state.setdefault("convergence", {})
    history = conv.setdefault("history", [])
    iter_n = int(state.get("cycle", len(history) + 1))

    entry = {
        "iter": iter_n,
        "wns_ns": curr_report["timing"]["wns_ns"],
        "power_mw": curr_report["power"]["total_mw"],
        "area_um2": curr_report["area"]["total_um2"],
        "weighted_delta_pct": None,
    }
    if history:
        prev_entry = history[-1]
        prev_report = {
            "timing": {"wns_ns": prev_entry["wns_ns"]},
            "power": {"total_mw": prev_entry["power_mw"]},
            "area": {"total_um2": prev_entry["area_um2"]},
        }
        entry["weighted_delta_pct"] = weighted_delta(
            curr_report, prev_report, targets, weights, clock_hz=clock_hz
        )
    history.append(entry)

    # Timing regression guard: if WNS worsens by more than 20 ps, short-circuit.
    if len(history) >= 2:
        delta_wns = history[-1]["wns_ns"] - history[-2]["wns_ns"]
        if delta_wns < -0.02:
            state["convergence"]["timing_regression"] = {
                "iter": iter_n,
                "delta_wns": delta_wns,
            }
            return "TIMING_REGRESSION"

    conv["targets_met"] = targets_met(curr_report, targets)

    delta_pct = float(conv.get("delta_pct", 2.0))
    streak_req = int(conv.get("streak_required", 3))
    early_pct = float(conv.get("early_plateau_pct", 1.0))
    max_cycles = int(state.get("max_cycles", 4))

    with_delta = [h for h in history if h["weighted_delta_pct"] is not None]
    current_streak = 0
    for h in reversed(with_delta):
        if abs(h["weighted_delta_pct"]) < delta_pct:
            current_streak += 1
        else:
            break
    conv["current_streak"] = current_streak

    if all(conv["targets_met"].values()):
        return "CONVERGED_TARGETS"
    if current_streak >= streak_req:
        return "CONVERGED_STREAK"
    if iter_n <= 2 and with_delta and all(
        abs(h["weighted_delta_pct"]) < early_pct
        for h in with_delta[-min(2, len(with_delta)) :]
    ):
        return "EARLY_PLATEAU"
    if iter_n >= max_cycles:
        return "MAX_CYCLES"
    return "CONTINUE"


def main(argv):
    if len(argv) < 4:
        print(
            "Usage: compute_delta.py <curr.json> <state.json> <requirements.json>",
            file=sys.stderr,
        )
        return 1
    curr = load_json(argv[1])
    state_path = argv[2]
    req = load_json(argv[3])
    targets = req.get("ppa_targets", {})
    weights = targets.get("weights", {"timing": 0.7, "power": 0.2, "area": 0.1})
    clock_hz = req.get("clock_hz")

    # Use a dedicated lock file that never moves so the lock remains valid
    # across os.replace (which swaps the state file's inode).
    lock_path = str(state_path) + ".lock"
    with open(lock_path, "a") as lock_f:      # "a" so we neither truncate nor require pre-existence
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            state = load_json(state_path)     # now safe inside critical section
            verdict = evaluate_convergence(state, curr, targets, weights, clock_hz=clock_hz)
            if verdict not in VALID_VERDICTS:
                print(f"Internal error: invalid verdict '{verdict}'", file=sys.stderr)
                return 2
            dir_ = os.path.dirname(state_path) or "."
            fd, tmp_path = tempfile.mkstemp(prefix=".ppa-state-", dir=dir_)
            try:
                with os.fdopen(fd, "w") as tmp_f:
                    json.dump(state, tmp_f, indent=2)
                os.replace(tmp_path, state_path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
