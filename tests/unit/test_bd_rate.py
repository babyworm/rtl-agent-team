"""Tests for bd_rate.py — BD-PSNR and BD-rate calculation."""

import json
import math
import sys
import warnings
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "codec-rd-eval" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from bd_rate import (
    bd_rate,
    bd_psnr,
    _validate_inputs,
    _poly_degrees,
    _integrate_poly,
    _sanitize_for_json,
    compute_metrics_from_results,
)


class TestValidateInputs:
    """Tests for input validation."""

    def test_too_few_anchor_points(self):
        with pytest.raises(ValueError, match="at least 3 anchor"):
            _validate_inputs([100, 200], [30, 33], [100, 200, 400], [30, 33, 36])

    def test_too_few_test_points(self):
        with pytest.raises(ValueError, match="at least 3 test"):
            _validate_inputs([100, 200, 400], [30, 33, 36], [100, 200], [30, 33])

    def test_length_mismatch_anchor(self):
        with pytest.raises(ValueError, match="Anchor rates.*length mismatch"):
            _validate_inputs([100, 200, 400], [30, 33], [100, 200, 400], [30, 33, 36])

    def test_length_mismatch_test(self):
        with pytest.raises(ValueError, match="Test rates.*length mismatch"):
            _validate_inputs([100, 200, 400], [30, 33, 36], [100, 200, 400], [30, 33])

    def test_zero_rate_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            _validate_inputs([0, 200, 400], [30, 33, 36], [100, 200, 400], [30, 33, 36])

    def test_negative_rate_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            _validate_inputs([-1, 200, 400], [30, 33, 36], [100, 200, 400], [30, 33, 36])

    def test_zero_psnr_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            _validate_inputs([100, 200, 400], [0, 33, 36], [100, 200, 400], [30, 33, 36])

    def test_valid_inputs_pass(self):
        _validate_inputs([100, 200, 400], [30, 33, 36], [100, 200, 400], [30, 33, 36])


class TestPolyDegrees:
    """Tests for polynomial degree selection."""

    def test_standard_4_points(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            deg_a, deg_t = _poly_degrees(4, 4)
        assert deg_a == 3
        assert deg_t == 3

    def test_3_points_quadratic(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            deg_a, deg_t = _poly_degrees(3, 3)
        assert deg_a == 2
        assert deg_t == 2
        assert len(w) == 1
        assert "Non-standard" in str(w[0].message)

    def test_5_points_cubic(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            deg_a, deg_t = _poly_degrees(5, 5)
        assert deg_a == 3
        assert deg_t == 3


class TestIntegratePoly:
    """Tests for polynomial integration."""

    def test_constant(self):
        # f(x) = 5 → integral from 0 to 2 = 10
        assert _integrate_poly([5], 0, 2) == pytest.approx(10.0)

    def test_linear(self):
        # f(x) = 2x + 1 → integral from 0 to 3 = [x^2 + x] from 0 to 3 = 9 + 3 = 12
        assert _integrate_poly([2, 1], 0, 3) == pytest.approx(12.0)

    def test_quadratic(self):
        # f(x) = x^2 → integral from 0 to 1 = 1/3
        assert _integrate_poly([1, 0, 0], 0, 1) == pytest.approx(1.0 / 3.0)


class TestBdRate:
    """Tests for BD-rate calculation."""

    def test_identical_curves_zero(self):
        """Identical RD curves should yield BD-rate ~0."""
        rates = [100, 200, 400, 800]
        psnrs = [30.0, 33.0, 36.0, 39.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = bd_rate(rates, psnrs, rates, psnrs)
        assert abs(result) < 0.01

    def test_better_test_negative_rate(self):
        """Test with lower bitrate at same quality → negative BD-rate."""
        anchor_rates = [200, 400, 800, 1600]
        anchor_psnrs = [30.0, 33.0, 36.0, 39.0]
        test_rates = [150, 300, 600, 1200]
        test_psnrs = [30.0, 33.0, 36.0, 39.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = bd_rate(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
        assert result < -10.0

    def test_worse_test_positive_rate(self):
        """Test with higher bitrate at same quality → positive BD-rate."""
        anchor_rates = [100, 200, 400, 800]
        anchor_psnrs = [32.0, 35.0, 38.0, 41.0]
        test_rates = [150, 300, 600, 1200]
        test_psnrs = [32.0, 35.0, 38.0, 41.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = bd_rate(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
        assert result > 10.0

    def test_near_identical_psnr_returns_nan(self):
        """Near-identical PSNR values should return NaN."""
        rates = [100, 200, 400, 800]
        psnrs = [36.0, 36.0, 36.0, 36.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = bd_rate(rates, psnrs, rates, [36.1, 36.1, 36.1, 36.1])
        assert math.isnan(result)


class TestBdPsnr:
    """Tests for BD-PSNR calculation."""

    def test_identical_curves_zero(self):
        rates = [100, 200, 400, 800]
        psnrs = [30.0, 33.0, 36.0, 39.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = bd_psnr(rates, psnrs, rates, psnrs)
        assert abs(result) < 0.01

    def test_better_quality_positive_psnr(self):
        """Better test quality at same rate → positive BD-PSNR."""
        anchor_rates = [100, 200, 400, 800]
        anchor_psnrs = [30.0, 33.0, 36.0, 39.0]
        test_rates = [100, 200, 400, 800]
        test_psnrs = [31.0, 34.0, 37.0, 40.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = bd_psnr(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
        assert result > 0.5


class TestSanitizeForJson:
    """Tests for NaN/Inf JSON sanitization."""

    def test_nan_replaced(self):
        assert _sanitize_for_json(float('nan')) is None

    def test_inf_replaced(self):
        assert _sanitize_for_json(float('inf')) is None

    def test_neg_inf_replaced(self):
        assert _sanitize_for_json(float('-inf')) is None

    def test_normal_float_preserved(self):
        assert _sanitize_for_json(3.14) == pytest.approx(3.14)

    def test_nested_dict(self):
        obj = {"a": float('nan'), "b": {"c": float('inf'), "d": 42}}
        result = _sanitize_for_json(obj)
        assert result == {"a": None, "b": {"c": None, "d": 42}}

    def test_list(self):
        result = _sanitize_for_json([1.0, float('nan'), 3.0])
        assert result == [1.0, None, 3.0]

    def test_serializable_after_sanitize(self):
        """Sanitized output must be valid JSON."""
        obj = {"val": float('nan'), "nested": [float('inf')]}
        sanitized = _sanitize_for_json(obj)
        json_str = json.dumps(sanitized)
        assert '"val": null' in json_str


class TestComputeMetricsFromResults:
    """Tests for compute_metrics_from_results()."""

    def test_basic_two_config(self, rd_results_sample):
        metrics = compute_metrics_from_results(str(rd_results_sample))
        assert metrics["anchor_label"] == "anchor"
        assert metrics["test_label"] == "test"
        assert "BasketballDrill" in metrics["sequences"]
        seq = metrics["sequences"]["BasketballDrill"]
        # Test is better → negative BD-rate
        assert seq["bd_rate_y"] < 0

    def test_aggregate_computed(self, rd_results_sample):
        metrics = compute_metrics_from_results(str(rd_results_sample))
        assert "aggregate" in metrics
        assert "avg_bd_rate_y" in metrics["aggregate"]

    def test_single_config_returns_error(self, tmp_path):
        results = [
            {"sequence": "seq", "qp": 22, "config_label": "only_one",
             "bitrate_kbps": 1000, "psnr_y": 36.0, "psnr_u": 38.0, "psnr_v": 38.0,
             "psnr_yuv": 36.0, "encode_time_s": 1.0, "status": "success"},
        ]
        path = tmp_path / "results.json"
        path.write_text(json.dumps(results))
        metrics = compute_metrics_from_results(str(path))
        assert "error" in metrics
