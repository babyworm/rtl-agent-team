"""Integration test for PPA optimization loop state transitions.

Exercises compute_delta.py against a simulated history that goes through
CONTINUE → CONVERGED_STREAK. Does not require DC or git.
"""
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "rtl-ppa-optimize-dc" / "scripts"


def _write_report(path, wns, power, area):
    report = {
        "schema_version": "1.1",
        "tool": "dc_shell",
        "design": "stub",
        "iteration": 1,
        "timestamp": "2026-04-17T00:00:00Z",
        "liberty": "",
        "sdc": "",
        "area": {"total_um2": area, "per_module": []},
        "timing": {"clock": "sys_clk", "period_ns": 1.25, "wns_ns": wns,
                   "tns_ns": 0.0, "num_violating_paths": 0, "critical_paths": []},
        "power": {"total_mw": power, "dynamic_mw": power*0.8, "leakage_mw": power*0.2,
                  "clock_mw": power*0.33, "clock_pct": 33.0, "net_mw": 0, "internal_mw": power*0.15, "register_mw": 0,
                  "combinational_mw": 0, "macro_mw": 0, "analysis_effort": "high", "per_module": []},
        "qor": {"design_wns_ns": wns, "design_tns_ns": 0, "worst_hold_slack_ns": 0, "status": "PASS"},
        "clock_gating": {"total_registers": 100, "gated_registers": 80, "gating_efficiency_pct": 80.0, "ungated_banks": []},
        "vt_group": {"LVT_pct": 5, "SVT_pct": 60, "HVT_pct": 35},
        "warnings": [],
    }
    pathlib.Path(path).write_text(json.dumps(report, indent=2))


def _initial_state(cycle=1, max_cycles=4):
    return {
        "mode": "ppa-loop",
        "cycle": cycle,
        "max_cycles": max_cycles,
        "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
        "convergence": {
            "delta_pct": 2.0,
            "streak_required": 3,
            "early_plateau_pct": 1.0,
            "history": [],
        },
        "allowed_edit_scope": ["rtl/stub/**/*.sv"],
        "frozen_scope": ["rtl/common/**"],
        "last_cycle_timestamp": 0,
        "auto_continue_minutes": 30,
    }


def _requirements():
    return {
        "top_module": "stub",
        "clock_hz": 800000000,
        "ppa_targets": {
            "power_mw": 100.0,
            "timing_slack_ns": 0.10,
            "area_um2": 50000.0,
            "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
            "convergence": {
                "delta_pct": 2.0,
                "streak": 3,
                "early_plateau_pct": 1.0,
                "max_cycles": 4,
            },
        },
    }


def _run_compute_delta(curr, state, req):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "compute_delta.py"),
         str(curr), str(state), str(req)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr


def test_loop_progression_to_streak_convergence(tmp_path):
    state = tmp_path / "state.json"
    req = tmp_path / "requirements.json"
    req.write_text(json.dumps(_requirements()))

    # --- iter 1: baseline
    s = _initial_state(cycle=1)
    state.write_text(json.dumps(s))
    curr = tmp_path / "iter1.json"
    _write_report(curr, -0.12, 135.0, 48000.0)
    rc, out, err = _run_compute_delta(curr, state, req)
    assert rc == 0, err
    assert out == "CONTINUE"

    # --- iter 2: small improvement (not yet converged)
    s = json.loads(state.read_text())
    s["cycle"] = 2
    state.write_text(json.dumps(s))
    curr = tmp_path / "iter2.json"
    _write_report(curr, -0.095, 130.0, 47500.0)
    rc, out, err = _run_compute_delta(curr, state, req)
    assert rc == 0, err
    assert out in ("CONTINUE", "EARLY_PLATEAU")

    # --- iter 3-5: small deltas — should reach CONVERGED_STREAK
    final_out = None
    for cycle, (w, p, a) in [(3, (-0.094, 129.5, 47300.0)),
                              (4, (-0.093, 129.2, 47200.0)),
                              (5, (-0.093, 129.0, 47100.0))]:
        s = json.loads(state.read_text())
        s["cycle"] = cycle
        state.write_text(json.dumps(s))
        curr = tmp_path / f"iter{cycle}.json"
        _write_report(curr, *(w, p, a))
        rc, out, err = _run_compute_delta(curr, state, req)
        assert rc == 0, err
        final_out = out
    # By iter 5, three consecutive small-delta iterations must have triggered convergence
    assert final_out == "CONVERGED_STREAK", (
        f"Expected CONVERGED_STREAK after 3 consecutive small-delta iterations, got {final_out!r}"
    )


def test_all_targets_met_triggers_converged_targets(tmp_path):
    state = tmp_path / "state.json"
    req = tmp_path / "requirements.json"
    req.write_text(json.dumps(_requirements()))
    s = _initial_state(cycle=2)
    state.write_text(json.dumps(s))
    curr = tmp_path / "targets_met.json"
    _write_report(curr, 0.15, 80.0, 44000.0)  # wns >= timing_slack_ns (0.10)
    rc, out, err = _run_compute_delta(curr, state, req)
    assert rc == 0, err
    assert out == "CONVERGED_TARGETS"
