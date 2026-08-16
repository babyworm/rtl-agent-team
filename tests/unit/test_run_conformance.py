"""Tests for run_conformance.py — Conformance stream discovery and decoding result parsing."""

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "codec-conformance-eval" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

from run_conformance import (
    discover_streams,
    compute_md5,
    filter_by_level,
    filter_by_profile,
    DecodingResult,
    STREAM_EXTENSIONS,
    _sanitize_for_json,
)


class TestDiscoverStreams:
    """Tests for discover_streams()."""

    def test_explicit_streams(self):
        source = {
            "id": "itu",
            "priority": "mandatory",
            "streams": [
                {"name": "CABAC_A", "path": "/data/CABAC_A.264"},
                {"name": "CABAC_B", "path": "/data/CABAC_B.264"},
            ],
        }
        result = discover_streams(source, "h264")
        assert len(result) == 2
        assert result[0]["name"] == "CABAC_A"
        assert result[0]["source_id"] == "itu"
        assert result[0]["priority"] == "mandatory"

    def test_explicit_streams_name_from_path(self):
        """When name is missing, derive from path stem."""
        source = {
            "id": "custom",
            "streams": [{"path": "/data/test_stream.264"}],
        }
        result = discover_streams(source, "h264")
        assert result[0]["name"] == "test_stream"

    def test_auto_discover_h264(self, tmp_path):
        stream_dir = tmp_path / "conformance"
        stream_dir.mkdir()
        (stream_dir / "CABAC_A.264").write_bytes(b"\x00" * 100)
        (stream_dir / "CABAC_B.h264").write_bytes(b"\x00" * 100)
        (stream_dir / "readme.txt").write_text("not a stream")

        source = {"id": "local", "path": str(stream_dir), "priority": "optional"}
        result = discover_streams(source, "h264")
        names = [s["name"] for s in result]
        assert "CABAC_A" in names
        assert "CABAC_B" in names
        assert len(result) == 2

    def test_auto_discover_h265(self, tmp_path):
        stream_dir = tmp_path / "hevc"
        stream_dir.mkdir()
        (stream_dir / "INTRA_A.265").write_bytes(b"\x00" * 100)
        (stream_dir / "INTER_B.hevc").write_bytes(b"\x00" * 100)

        source = {"id": "jct-vc", "path": str(stream_dir)}
        result = discover_streams(source, "h265")
        assert len(result) == 2

    def test_auto_discover_recursive(self, tmp_path):
        """Streams in subdirectories should be found."""
        base = tmp_path / "streams"
        sub = base / "main" / "level4"
        sub.mkdir(parents=True)
        (sub / "test.264").write_bytes(b"\x00")

        source = {"id": "nested", "path": str(base)}
        result = discover_streams(source, "h264")
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_nonexistent_path(self):
        source = {"id": "missing", "path": "/nonexistent/dir"}
        result = discover_streams(source, "h264")
        assert result == []

    def test_default_priority_optional(self, tmp_path):
        stream_dir = tmp_path / "streams"
        stream_dir.mkdir()
        (stream_dir / "test.264").write_bytes(b"\x00")

        source = {"id": "test", "path": str(stream_dir)}
        result = discover_streams(source, "h264")
        assert result[0]["priority"] == "optional"

    def test_no_duplicates_different_extensions(self, tmp_path):
        """Same stem with different extensions should not create duplicates."""
        stream_dir = tmp_path / "streams"
        stream_dir.mkdir()
        (stream_dir / "test.264").write_bytes(b"\x00")
        (stream_dir / "test.h264").write_bytes(b"\x00")

        source = {"id": "test", "path": str(stream_dir)}
        result = discover_streams(source, "h264")
        names = [s["name"] for s in result]
        assert names.count("test") == 1


class TestStreamExtensions:
    """Tests for STREAM_EXTENSIONS configuration."""

    def test_h264_extensions(self):
        exts = STREAM_EXTENSIONS["h264"]
        assert "*.264" in exts
        assert "*.h264" in exts

    def test_h265_extensions(self):
        exts = STREAM_EXTENSIONS["h265"]
        assert "*.265" in exts
        assert "*.hevc" in exts


class TestDecodingResult:
    """Tests for DecodingResult dataclass."""

    def test_successful_result(self):
        r = DecodingResult(
            stream_name="test", source_id="itu", source_priority="mandatory",
            status="success", md5_decoded="aabb", decode_time_s=1.5,
            output_path="/tmp/out.yuv",
        )
        assert r.status == "success"
        assert r.error is None

    def test_failed_result(self):
        r = DecodingResult(
            stream_name="test", source_id="itu", source_priority="optional",
            status="failed", error="Timeout",
        )
        assert r.status == "failed"
        assert r.md5_decoded is None


class TestComputeMd5:
    """Tests for compute_md5() in run_conformance."""

    def test_known_file(self, tmp_path):
        f = tmp_path / "test.yuv"
        f.write_bytes(b"yuv data here")
        result = compute_md5(str(f))
        assert result is not None
        assert len(result) == 32

    def test_nonexistent(self):
        assert compute_md5("/no/such/file") is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.yuv"
        f.write_bytes(b"")
        result = compute_md5(str(f))
        assert result is not None


class TestSanitizeForJson:
    """Tests for _sanitize_for_json in run_conformance."""

    def test_nan(self):
        assert _sanitize_for_json(float("nan")) is None

    def test_inf(self):
        assert _sanitize_for_json(float("inf")) is None

    def test_normal(self):
        assert _sanitize_for_json(3.14) == pytest.approx(3.14)

    def test_nested(self):
        obj = {"a": [float("nan"), 1.0], "b": {"c": float("inf")}}
        result = _sanitize_for_json(obj)
        assert result == {"a": [None, 1.0], "b": {"c": None}}
        json.dumps(result)  # Must be serializable


class TestProfileAndLevelFilters:
    """`target.level` is advertised in the config template and SKILL.md.

    v0.14.2: run_conformance.py read `target.level` into a local and never used
    it, so a run configured for a single level silently decoded every stream and
    reported success. The AWS Batch path did not read `level` at all, so the two
    execution modes selected different stream sets from the same config.
    """

    STREAMS = [
        {"name": "AVC_Baseline_L21_foreman"},
        {"name": "AVC_Main_L41_city"},
        {"name": "AVC_Main_4.1_harbour"},
        {"name": "AVC_Main_4_1_mobile"},
        {"name": "AVC_High_L50_park"},
        {"name": "AVC_Main_L411_x"},
        {"name": "AVC_Main_L14.11_y"},
    ]

    @staticmethod
    def _names(streams):
        return sorted(s["name"] for s in streams)

    def test_empty_level_disables_filtering(self):
        assert filter_by_level(self.STREAMS, "") == self.STREAMS

    def test_level_matches_packed_dotted_and_underscored_forms(self):
        assert self._names(filter_by_level(self.STREAMS, "4.1")) == [
            "AVC_Main_4.1_harbour",
            "AVC_Main_4_1_mobile",
            "AVC_Main_L41_city",
        ]

    def test_level_does_not_match_longer_neighbours(self):
        """`4.1` must not match inside `L411` or `L14.11`."""
        matched = self._names(filter_by_level(self.STREAMS, "4.1"))
        assert "AVC_Main_L411_x" not in matched
        assert "AVC_Main_L14.11_y" not in matched

    def test_empty_profile_disables_filtering(self):
        assert filter_by_profile(self.STREAMS, "") == self.STREAMS

    def test_profile_uses_word_boundaries(self):
        streams = [{"name": "AVC_Main_L41"}, {"name": "AVC_domain_L41"}]
        assert self._names(filter_by_profile(streams, "main")) == ["AVC_Main_L41"]

    def test_profile_and_level_compose(self):
        result = filter_by_level(filter_by_profile(self.STREAMS, "main"), "4.1")
        assert self._names(result) == [
            "AVC_Main_4.1_harbour",
            "AVC_Main_4_1_mobile",
            "AVC_Main_L41_city",
        ]

    def test_both_execution_paths_apply_both_filters(self):
        """run_local and run_aws_batch must select the same set from one config."""
        source = Path(__file__).resolve().parents[2] / "skills" / (
            "codec-conformance-eval") / "scripts" / "run_conformance.py"
        body = source.read_text()
        local = body.split("def run_local", 1)[1].split("def run_aws_batch", 1)[0]
        aws = body.split("def run_aws_batch", 1)[1].split("\ndef ", 1)[0]
        for name, section in (("run_local", local), ("run_aws_batch", aws)):
            assert "filter_by_profile" in section, f"{name} skips the profile filter"
            assert "filter_by_level" in section, f"{name} skips the level filter"
