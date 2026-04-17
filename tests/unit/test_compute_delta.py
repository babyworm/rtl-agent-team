"""Unit tests for compute_delta.py — weighted Δ + convergence verdict."""
import json
import pathlib
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "skills" / "rtl-ppa-optimize-dc" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import compute_delta as cd  # noqa: E402


def _report(wns, power_mw, area_um2):
    return {
        "timing": {"wns_ns": wns},
        "power": {"total_mw": power_mw},
        "area": {"total_um2": area_um2},
    }


def _state(cycle, max_cycles=4, history=None, streak_req=3, delta_pct=2.0, early_pct=1.0):
    return {
        "mode": "ppa-loop",
        "cycle": cycle,
        "max_cycles": max_cycles,
        "convergence": {
            "delta_pct": delta_pct,
            "streak_required": streak_req,
            "early_plateau_pct": early_pct,
            "history": history or [],
        },
    }


def _targets(period=1.25, power=100.0, area=50000.0):
    return {
        "timing_slack_ns": 0.10,
        "power_mw": power,
        "area_um2": area,
        "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
    }


class TestNormalizeWeights:
    def test_unit_sum(self):
        w = cd.normalize_weights({"timing": 0.7, "power": 0.2, "area": 0.1})
        assert pytest.approx(sum(w.values())) == 1.0

    def test_non_unit_sum(self):
        w = cd.normalize_weights({"timing": 7, "power": 2, "area": 1})
        assert w["timing"] == pytest.approx(0.7)
        assert w["power"] == pytest.approx(0.2)
        assert w["area"] == pytest.approx(0.1)

    def test_zero_sum_raises(self):
        with pytest.raises(ValueError):
            cd.normalize_weights({"timing": 0, "power": 0, "area": 0})


class TestWeightedDelta:
    def test_improvement_is_positive(self):
        prev = _report(-0.12, 135.0, 48000.0)
        curr = _report(-0.08, 127.0, 46000.0)
        delta = cd.weighted_delta(curr, prev, _targets(), _targets()["weights"])
        assert delta > 0

    def test_regression_is_negative(self):
        prev = _report(-0.08, 127.0, 46000.0)
        curr = _report(-0.12, 135.0, 48000.0)
        delta = cd.weighted_delta(curr, prev, _targets(), _targets()["weights"])
        assert delta < 0


class TestEvaluateConvergence:
    def test_first_iter_no_delta(self):
        state = _state(cycle=1)
        curr = _report(-0.12, 135.0, 48000.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "CONTINUE"
        assert state["convergence"]["history"][-1]["weighted_delta_pct"] is None

    def test_streak_convergence(self):
        history = [
            {"iter": 1, "wns_ns": -0.12, "power_mw": 135.0, "area_um2": 48000.0, "weighted_delta_pct": None},
            {"iter": 2, "wns_ns": -0.10, "power_mw": 132.0, "area_um2": 47500.0, "weighted_delta_pct": 1.2},
            {"iter": 3, "wns_ns": -0.095, "power_mw": 130.0, "area_um2": 47200.0, "weighted_delta_pct": 1.0},
        ]
        state = _state(cycle=4, history=history)
        curr = _report(-0.094, 129.5, 47100.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "CONVERGED_STREAK"

    def test_all_targets_met(self):
        state = _state(cycle=2)
        curr = _report(0.15, 80.0, 44000.0)  # wns=0.15 >= timing_slack_ns=0.10
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "CONVERGED_TARGETS"

    def test_converged_targets_respects_timing_slack(self):
        """wns=0.05 with target=0.10 must NOT declare CONVERGED_TARGETS."""
        state = _state(cycle=2)
        curr = _report(0.05, 80.0, 44000.0)  # slack 0.05 < target 0.10
        t = _targets()
        t["timing_slack_ns"] = 0.10
        verdict = cd.evaluate_convergence(state, curr, t, t["weights"])
        assert verdict != "CONVERGED_TARGETS"

    def test_converged_targets_at_or_above_slack(self):
        """wns=0.15 with target=0.10 (and power/area met) must declare CONVERGED_TARGETS."""
        state = _state(cycle=2)
        curr = _report(0.15, 80.0, 44000.0)
        t = _targets()
        t["timing_slack_ns"] = 0.10
        verdict = cd.evaluate_convergence(state, curr, t, t["weights"])
        assert verdict == "CONVERGED_TARGETS"

    def test_early_plateau(self):
        history = [
            {"iter": 1, "wns_ns": -0.12, "power_mw": 135.0, "area_um2": 48000.0, "weighted_delta_pct": None},
        ]
        state = _state(cycle=2, history=history)
        curr = _report(-0.1195, 134.8, 47990.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "EARLY_PLATEAU"

    def test_max_cycles(self):
        history = [
            {"iter": i, "wns_ns": -0.1, "power_mw": 130.0, "area_um2": 47000.0, "weighted_delta_pct": 3.0}
            for i in range(1, 4)
        ]
        state = _state(cycle=4, max_cycles=4, history=history)
        curr = _report(-0.08, 125.0, 46500.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "MAX_CYCLES"

    def test_timing_regression_verdict_triggers(self):
        # prev WNS = -0.1, curr WNS = -0.15: 50 ps worse → TIMING_REGRESSION
        history = [
            {"iter": 1, "wns_ns": -0.1, "power_mw": 130.0, "area_um2": 47000.0, "weighted_delta_pct": None},
        ]
        state = _state(cycle=2, history=history)
        # Power improves (130 → 120), area improves, but timing gets 50 ps worse
        curr = _report(-0.15, 120.0, 46000.0)
        verdict = cd.evaluate_convergence(state, curr, _targets(), _targets()["weights"])
        assert verdict == "TIMING_REGRESSION"
        reg = state["convergence"]["timing_regression"]
        assert reg["delta_wns"] < 0
        assert reg["iter"] == 2
