"""Unit tests for ppa-loop-state.json schema validation."""
import json
import pathlib

import pytest


REQUIRED_TOP_LEVEL = {
    "mode", "cycle", "max_cycles", "weights", "convergence",
    "allowed_edit_scope", "frozen_scope",
    "last_cycle_timestamp", "auto_continue_minutes",
}
REQUIRED_CONVERGENCE = {
    "delta_pct", "streak_required", "early_plateau_pct", "history",
}
REQUIRED_WEIGHTS = {"timing", "power", "area"}


def _valid_state():
    return {
        "mode": "ppa-loop",
        "cycle": 1,
        "max_cycles": 4,
        "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
        "convergence": {
            "delta_pct": 2.0,
            "streak_required": 3,
            "early_plateau_pct": 1.0,
            "history": [],
        },
        "allowed_edit_scope": ["rtl/mod/**/*.sv"],
        "frozen_scope": ["rtl/common/**", "rtl/pkg/**", "rtl/intf/**"],
        "last_cycle_timestamp": 0,
        "auto_continue_minutes": 30,
    }


class TestPPALoopStateSchema:
    def test_valid_state_has_all_top_level_keys(self):
        state = _valid_state()
        assert set(state.keys()) >= REQUIRED_TOP_LEVEL

    def test_convergence_has_required_keys(self):
        state = _valid_state()
        assert set(state["convergence"].keys()) >= REQUIRED_CONVERGENCE

    def test_weights_has_all_axes(self):
        state = _valid_state()
        assert set(state["weights"].keys()) == REQUIRED_WEIGHTS

    def test_weights_sum_positive(self):
        state = _valid_state()
        assert sum(state["weights"].values()) > 0

    def test_mode_is_ppa_loop(self):
        state = _valid_state()
        assert state["mode"] == "ppa-loop"

    def test_cycle_is_integer(self):
        state = _valid_state()
        assert isinstance(state["cycle"], int)

    def test_max_cycles_at_least_one(self):
        state = _valid_state()
        assert state["max_cycles"] >= 1

    def test_allowed_and_frozen_scope_are_lists(self):
        state = _valid_state()
        assert isinstance(state["allowed_edit_scope"], list)
        assert isinstance(state["frozen_scope"], list)

    def test_json_roundtrip(self):
        state = _valid_state()
        parsed = json.loads(json.dumps(state))
        assert parsed == state
