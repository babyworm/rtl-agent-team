"""Tests for run_eval.py — Encoder output parsing and config resolution."""

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "codec-rd-eval" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from run_eval import (
    parse_encoder_output,
    sanitize_label,
    _resolve_configs,
    _sanitize_for_json,
    CHROMA_WEIGHTS,
)


class TestParseEncoderOutput:
    """Tests for parse_encoder_output()."""

    def test_hm_style_output(self, encoder_output_hm_style):
        result = parse_encoder_output(encoder_output_hm_style, "")
        assert result["bitrate_kbps"] == pytest.approx(1234.56)
        assert result["psnr_y"] == pytest.approx(36.45)
        assert result["psnr_u"] == pytest.approx(40.12)
        assert result["psnr_v"] == pytest.approx(41.34)
        assert result["psnr_yuv"] == pytest.approx(37.21)

    def test_weighted_yuv_fallback(self):
        """When PSNR-YUV is not in output, it should be computed from Y/U/V."""
        output = "Bitrate: 500.0 kbps\nPSNR-Y: 36.0\nPSNR-U: 40.0\nPSNR-V: 42.0\n"
        result = parse_encoder_output(output, "")
        # 420 weighting: (6*36 + 1*40 + 1*42) / 8 = (216+40+42)/8 = 37.25
        assert result["psnr_yuv"] == pytest.approx(37.25)

    def test_422_weighting(self):
        output = "Bitrate: 500.0 kbps\nPSNR-Y: 36.0\nPSNR-U: 40.0\nPSNR-V: 42.0\n"
        result = parse_encoder_output(output, "", chroma_format="422")
        wy, wu, wv = CHROMA_WEIGHTS["422"]
        expected = (wy * 36.0 + wu * 40.0 + wv * 42.0) / (wy + wu + wv)
        assert result["psnr_yuv"] == pytest.approx(expected)

    def test_444_weighting(self):
        output = "Bitrate: 500.0 kbps\nPSNR-Y: 36.0\nPSNR-U: 40.0\nPSNR-V: 42.0\n"
        result = parse_encoder_output(output, "", chroma_format="444")
        expected = (36.0 + 40.0 + 42.0) / 3.0
        assert result["psnr_yuv"] == pytest.approx(expected)

    def test_custom_parsing_patterns(self):
        output = "rate=800.5bps quality_y=38.2dB"
        custom = {
            "bitrate_pattern": r"rate=([0-9.]+)",
            "psnr_y_pattern": r"quality_y=([0-9.]+)",
        }
        result = parse_encoder_output(output, "", parsing_config=custom)
        assert result["bitrate_kbps"] == pytest.approx(800.5)
        assert result["psnr_y"] == pytest.approx(38.2)

    def test_empty_output(self):
        result = parse_encoder_output("", "")
        assert result["bitrate_kbps"] == 0.0
        assert result["psnr_y"] == 0.0
        assert result["psnr_yuv"] == 0.0

    def test_invalid_regex_pattern_handled(self):
        """Invalid user-provided regex should not crash."""
        output = "Bitrate: 500.0 kbps\nPSNR-Y: 36.0\n"
        custom = {"bitrate_pattern": "[invalid(regex"}
        result = parse_encoder_output(output, "", parsing_config=custom)
        # Falls back to default: bitrate_kbps should still be parsed from default
        # Actually with custom pattern, it uses the custom one which is invalid
        assert result["bitrate_kbps"] == 0.0  # invalid regex → no match

    def test_ssim_parsing(self):
        output = "Bitrate: 500.0 kbps\nPSNR-Y: 36.0\nSSIM: 0.9523\n"
        result = parse_encoder_output(output, "")
        assert result["ssim"] == pytest.approx(0.9523)

    def test_stderr_also_parsed(self):
        result = parse_encoder_output("", "Bitrate: 750.0 kbps\nPSNR-Y: 34.0\n")
        assert result["bitrate_kbps"] == pytest.approx(750.0)
        assert result["psnr_y"] == pytest.approx(34.0)

    def test_overly_long_regex_rejected(self):
        """Regex longer than 500 chars should be skipped."""
        output = "Bitrate: 500.0 kbps\n"
        custom = {"bitrate_pattern": "a" * 501}
        result = parse_encoder_output(output, "", parsing_config=custom)
        assert result["bitrate_kbps"] == 0.0


class TestSanitizeLabel:
    """Tests for sanitize_label()."""

    def test_basic(self):
        assert sanitize_label("anchor_config") == "anchor_config"

    def test_spaces_replaced(self):
        assert "_" in sanitize_label("my config name")

    def test_special_chars_replaced(self):
        result = sanitize_label("config/v2@test")
        assert "/" not in result
        assert "@" not in result

    def test_long_label_truncated_with_hash(self):
        long_label = "a" * 100
        result = sanitize_label(long_label)
        assert len(result) <= 64

    def test_empty_string(self):
        assert sanitize_label("") == "unnamed"


class TestResolveConfigs:
    """Tests for _resolve_configs()."""

    def test_anchor_test_pair(self):
        config = {
            "anchor": {"encoder_binary": "/bin/enc", "label": "anchor"},
            "test": {"encoder_binary": "/bin/enc2", "label": "test"},
        }
        result = _resolve_configs(config)
        assert len(result) == 2
        assert result[0][1] is True  # anchor
        assert result[1][1] is False  # test

    def test_candidates_array(self):
        config = {
            "candidates": [
                {"label": "config_a", "is_anchor": True},
                {"label": "config_b"},
                {"label": "config_c"},
            ]
        }
        result = _resolve_configs(config)
        assert len(result) == 3
        assert result[0][1] is True  # explicit anchor

    def test_candidates_no_explicit_anchor(self):
        """First candidate becomes anchor if none marked."""
        config = {
            "candidates": [
                {"label": "config_a"},
                {"label": "config_b"},
            ]
        }
        result = _resolve_configs(config)
        assert result[0][1] is True  # first becomes anchor

    def test_empty_config(self):
        result = _resolve_configs({})
        assert result == []

    def test_single_candidate_warning(self):
        """Single candidate should trigger a warning."""
        import warnings
        config = {"candidates": [{"label": "only_one"}]}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _resolve_configs(config)
        assert any("only 1 entry" in str(warning.message) for warning in w)
