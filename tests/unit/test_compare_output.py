"""Tests for compare_output.py — Conformance comparison functions."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "codec-conformance-eval" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

from compare_output import (
    compare_bitexact,
    compare_md5,
    compute_md5,
    load_golden_md5s,
    _sanitize_for_json,
)


class TestCompareMd5:
    """Tests for MD5 checksum comparison."""

    def test_match(self):
        result = compare_md5("abc123def456", "abc123def456")
        assert result["match"] is True

    def test_mismatch(self):
        result = compare_md5("abc123", "def456")
        assert result["match"] is False

    def test_none_decoded(self):
        result = compare_md5(None, "abc123")
        assert result["match"] is False

    def test_none_golden(self):
        result = compare_md5("abc123", None)
        assert result["match"] is False

    def test_both_none(self):
        result = compare_md5(None, None)
        assert result["match"] is False


class TestComputeMd5:
    """Tests for file MD5 computation."""

    def test_known_content(self, tmp_path):
        f = tmp_path / "test.bin"
        content = b"test data for md5"
        f.write_bytes(content)
        expected = hashlib.md5(content, usedforsecurity=False).hexdigest()
        assert compute_md5(str(f)) == expected

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        result = compute_md5(str(f))
        assert result is not None
        assert len(result) == 32

    def test_nonexistent_file(self):
        result = compute_md5("/nonexistent/path/file.bin")
        assert result is None

    def test_large_file(self, tmp_path):
        """Files larger than one chunk (8192 bytes) should be handled."""
        f = tmp_path / "large.bin"
        f.write_bytes(b"\x42" * 20000)
        result = compute_md5(str(f))
        assert result is not None
        assert len(result) == 32


class TestCompareBitexact:
    """Tests for byte-by-byte comparison."""

    def test_identical_files(self, tmp_path):
        data = b"\x00\x01\x02\x03" * 100
        fa = tmp_path / "a.bin"
        fb = tmp_path / "b.bin"
        fa.write_bytes(data)
        fb.write_bytes(data)
        result = compare_bitexact(str(fa), str(fb))
        assert result["match"] is True
        assert result["first_mismatch_offset"] is None

    def test_different_content(self, tmp_path):
        fa = tmp_path / "a.bin"
        fb = tmp_path / "b.bin"
        fa.write_bytes(b"\x00\x01\x02\x03")
        fb.write_bytes(b"\x00\x01\xFF\x03")
        result = compare_bitexact(str(fa), str(fb))
        assert result["match"] is False
        assert result["first_mismatch_offset"] == 2

    def test_different_sizes(self, tmp_path):
        fa = tmp_path / "a.bin"
        fb = tmp_path / "b.bin"
        fa.write_bytes(b"\x00\x01\x02")
        fb.write_bytes(b"\x00\x01\x02\x03\x04")
        result = compare_bitexact(str(fa), str(fb))
        assert result["match"] is False

    def test_missing_file(self):
        result = compare_bitexact("/nonexistent/a.bin", "/nonexistent/b.bin")
        assert result["match"] is False
        assert "error" in result

    def test_empty_identical_files(self, tmp_path):
        fa = tmp_path / "a.bin"
        fb = tmp_path / "b.bin"
        fa.write_bytes(b"")
        fb.write_bytes(b"")
        result = compare_bitexact(str(fa), str(fb))
        assert result["match"] is True

    def test_mismatch_across_chunk_boundary(self, tmp_path):
        """Mismatch at byte 8193 (second chunk) should be detected."""
        fa = tmp_path / "a.bin"
        fb = tmp_path / "b.bin"
        data = b"\x00" * 8193
        fa.write_bytes(data)
        fb.write_bytes(data[:-1] + b"\xFF")
        result = compare_bitexact(str(fa), str(fb))
        assert result["match"] is False
        assert result["first_mismatch_offset"] == 8192


class TestLoadGoldenMd5s:
    """Tests for golden MD5 loading."""

    def test_json_file(self, tmp_path):
        golden = {"stream_a": "aabbccdd", "stream_b": "11223344"}
        f = tmp_path / "golden.json"
        f.write_text(json.dumps(golden))
        result = load_golden_md5s(str(f))
        assert result == golden

    def test_directory_with_md5_files(self, tmp_path):
        md5_dir = tmp_path / "golden"
        md5_dir.mkdir()
        (md5_dir / "stream_a.md5").write_text("aabbccdd  stream_a.yuv\n")
        (md5_dir / "stream_b.md5").write_text("11223344  stream_b.yuv\n")
        result = load_golden_md5s(str(md5_dir))
        assert result["stream_a"] == "aabbccdd"
        assert result["stream_b"] == "11223344"

    def test_nonexistent_path(self):
        result = load_golden_md5s("/nonexistent/path")
        assert result == {}

    def test_directory_with_md5sum_format(self, tmp_path):
        md5_dir = tmp_path / "golden"
        md5_dir.mkdir()
        (md5_dir / "checksum.md5sum").write_text(
            "aabbccdd  stream_a.yuv\n"
            "11223344  stream_b.yuv\n"
        )
        result = load_golden_md5s(str(md5_dir))
        assert "stream_a" in result
        assert "stream_b" in result
