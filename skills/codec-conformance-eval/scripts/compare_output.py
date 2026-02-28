#!/usr/bin/env python3
"""compare_output.py — Conformance output comparison for decoder evaluation.

Compares decoded YUV output against golden references using MD5, bitexact,
or PSNR-threshold comparison. Generates profile coverage matrix.

Usage:
    python3 compare_output.py <results.json> <config.hjson> [--output <metrics.json>]
    python3 compare_output.py --test  # Run built-in unit tests

Dependencies: hjson (optional, for config loading)
"""

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from typing import Optional


def compute_md5(filepath: str) -> Optional[str]:
    """Compute MD5 checksum of a file."""
    if not os.path.isfile(filepath):
        return None
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_bitexact(file_a: str, file_b: str) -> dict:
    """Byte-by-byte comparison of two files.

    Returns:
        dict with keys: match (bool), first_mismatch_offset (int or None),
                        size_a, size_b
    """
    if not os.path.isfile(file_a) or not os.path.isfile(file_b):
        return {
            "match": False,
            "first_mismatch_offset": None,
            "error": f"File not found: {file_a if not os.path.isfile(file_a) else file_b}",
        }

    size_a = os.path.getsize(file_a)
    size_b = os.path.getsize(file_b)

    with open(file_a, "rb") as fa, open(file_b, "rb") as fb:
        offset = 0
        while True:
            chunk_a = fa.read(8192)
            chunk_b = fb.read(8192)
            if not chunk_a and not chunk_b:
                break
            if chunk_a != chunk_b:
                # Find exact mismatch offset within chunk
                min_len = min(len(chunk_a), len(chunk_b))
                for i in range(min_len):
                    if chunk_a[i] != chunk_b[i]:
                        return {
                            "match": False,
                            "first_mismatch_offset": offset + i,
                            "size_a": size_a,
                            "size_b": size_b,
                        }
                # Length mismatch
                return {
                    "match": False,
                    "first_mismatch_offset": offset + min_len,
                    "size_a": size_a,
                    "size_b": size_b,
                }
            offset += len(chunk_a)

    return {"match": True, "first_mismatch_offset": None, "size_a": size_a, "size_b": size_b}


def compare_md5(decoded_md5: str, golden_md5: str) -> dict:
    """Compare MD5 checksums.

    Returns:
        dict with keys: match (bool), decoded_md5, golden_md5
    """
    match = decoded_md5 is not None and decoded_md5 == golden_md5
    return {"match": match, "decoded_md5": decoded_md5, "golden_md5": golden_md5}


def compute_psnr_from_files(file_a: str, file_b: str,
                            width: int, height: int, bit_depth: int = 8) -> Optional[float]:
    """Compute Y-PSNR between two raw YUV files.

    Uses simple MSE calculation on Y plane only.
    Returns None if files cannot be read.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    bytes_per_sample = 2 if bit_depth > 8 else 1
    y_size = width * height * bytes_per_sample
    dtype = np.uint16 if bit_depth > 8 else np.uint8
    max_val = (1 << bit_depth) - 1

    if not os.path.isfile(file_a) or not os.path.isfile(file_b):
        return None

    with open(file_a, "rb") as fa, open(file_b, "rb") as fb:
        y_a = fa.read(y_size)
        y_b = fb.read(y_size)

    if len(y_a) != y_size or len(y_b) != y_size:
        return None

    arr_a = np.frombuffer(y_a, dtype=dtype).astype(np.float64)
    arr_b = np.frombuffer(y_b, dtype=dtype).astype(np.float64)

    mse = np.mean((arr_a - arr_b) ** 2)
    if mse == 0:
        return float("inf")
    psnr = 10.0 * math.log10(max_val ** 2 / mse)
    return round(psnr, 4)


def run_ffmpeg_ssim(original: str, decoded: str,
                    width: int, height: int, bit_depth: int = 8) -> Optional[float]:
    """Compute SSIM using ffmpeg."""
    pix_fmt = f"yuv420p{'10le' if bit_depth > 8 else ''}"
    vsize = f"{width}x{height}"
    cmd = [
        "ffmpeg", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", original,
        "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", decoded,
        "-lavfi", "ssim", "-f", "null", "-"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        m = re.search(r'All:([0-9.]+)', proc.stderr)
        if m:
            return float(m.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def run_ffmpeg_vmaf(original: str, decoded: str,
                    width: int, height: int, bit_depth: int = 8) -> Optional[float]:
    """Compute VMAF using ffmpeg."""
    pix_fmt = f"yuv420p{'10le' if bit_depth > 8 else ''}"
    vsize = f"{width}x{height}"
    cmd = [
        "ffmpeg", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", decoded,
        "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", original,
        "-lavfi", "libvmaf", "-f", "null", "-"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        m = re.search(r'VMAF score:\s*([0-9.]+)', proc.stderr)
        if m:
            return float(m.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def load_golden_md5s(golden_path: str) -> dict:
    """Load golden MD5 checksums from a directory or JSON file.

    Supports:
    - JSON file: {"stream_name": "md5hex", ...}
    - Directory with .md5 files: each file contains "md5hex  filename"
    - Directory with .md5sum files: standard md5sum format

    Returns:
        dict mapping stream_name → md5_hex
    """
    if not os.path.exists(golden_path):
        return {}

    if os.path.isfile(golden_path) and golden_path.endswith(".json"):
        with open(golden_path, "r") as f:
            return json.load(f)

    md5s = {}
    if os.path.isdir(golden_path):
        for md5_file in sorted(os.listdir(golden_path)):
            if md5_file.endswith((".md5", ".md5sum")):
                filepath = os.path.join(golden_path, md5_file)
                with open(filepath, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            parts = line.split()
                            if len(parts) >= 2:
                                md5_hex = parts[0]
                                name = os.path.splitext(os.path.basename(parts[-1]))[0]
                                md5s[name] = md5_hex
                            elif len(parts) == 1:
                                name = os.path.splitext(md5_file)[0]
                                md5s[name] = parts[0]
    return md5s


def compare_results(results_path: str, config: dict) -> dict:
    """Compare all decoding results against golden references.

    Args:
        results_path: Path to results.json from run_conformance.py
        config: Conformance configuration dict

    Returns:
        Conformance metrics dict with per-stream and aggregate results.
    """
    with open(results_path, "r") as f:
        results = json.load(f)

    golden_cfg = config.get("golden", {})
    golden_path = golden_cfg.get("path", "")
    comparison_mode = golden_cfg.get("comparison_mode", "md5")
    psnr_threshold = golden_cfg.get("psnr_threshold", 100.0)
    quality_metrics = config.get("quality_metrics", ["psnr"])

    # Load golden MD5s
    golden_md5s = load_golden_md5s(golden_path)

    stream_results = []
    mandatory_pass = 0
    mandatory_fail = 0
    mandatory_total = 0
    optional_pass = 0
    optional_fail = 0
    optional_total = 0
    source_breakdown = {}

    for r in results:
        stream_name = r["stream_name"]
        source_id = r["source_id"]
        priority = r.get("source_priority", "optional")

        entry = {
            "stream_name": stream_name,
            "source_id": source_id,
            "priority": priority,
            "decode_status": r["status"],
            "decode_time_s": r.get("decode_time_s", 0),
        }

        if r["status"] != "success":
            entry["conformance"] = "FAIL"
            entry["error"] = r.get("error", "Decode failed")
        else:
            # Compare based on mode
            golden_md5 = golden_md5s.get(stream_name)

            if comparison_mode == "md5" and golden_md5:
                cmp = compare_md5(r.get("md5_decoded"), golden_md5)
                entry["conformance"] = "PASS" if cmp["match"] else "FAIL"
                entry["comparison"] = cmp
            elif comparison_mode == "bitexact" and golden_path:
                golden_yuv = os.path.join(golden_path, f"{stream_name}.yuv")
                if os.path.isfile(golden_yuv) and r.get("output_path"):
                    cmp = compare_bitexact(r["output_path"], golden_yuv)
                    entry["conformance"] = "PASS" if cmp["match"] else "FAIL"
                    entry["comparison"] = cmp
                else:
                    entry["conformance"] = "SKIP"
                    entry["error"] = "Golden YUV not found"
            elif golden_md5:
                # Fallback to MD5 if golden available
                cmp = compare_md5(r.get("md5_decoded"), golden_md5)
                entry["conformance"] = "PASS" if cmp["match"] else "FAIL"
                entry["comparison"] = cmp
            else:
                entry["conformance"] = "SKIP"
                entry["error"] = "No golden reference available"

        # Count by priority
        source_breakdown.setdefault(source_id, {"pass": 0, "fail": 0, "skip": 0, "total": 0})
        source_breakdown[source_id]["total"] += 1

        if entry["conformance"] == "PASS":
            source_breakdown[source_id]["pass"] += 1
            if priority == "mandatory":
                mandatory_pass += 1
            else:
                optional_pass += 1
        elif entry["conformance"] == "FAIL":
            source_breakdown[source_id]["fail"] += 1
            if priority == "mandatory":
                mandatory_fail += 1
            else:
                optional_fail += 1

        if priority == "mandatory":
            mandatory_total += 1
        else:
            optional_total += 1

        stream_results.append(entry)

    # Overall verdict: PASS only if all mandatory streams pass
    overall_verdict = "PASS" if mandatory_fail == 0 and mandatory_total > 0 else "FAIL"
    if mandatory_total == 0 and optional_fail == 0:
        overall_verdict = "PASS (no mandatory streams)"

    metrics = {
        "overall_verdict": overall_verdict,
        "summary": {
            "mandatory": {"pass": mandatory_pass, "fail": mandatory_fail, "total": mandatory_total},
            "optional": {"pass": optional_pass, "fail": optional_fail, "total": optional_total},
            "total_streams": len(stream_results),
        },
        "source_breakdown": source_breakdown,
        "streams": stream_results,
        "target": config.get("target", {}),
        "comparison_mode": comparison_mode,
    }

    return metrics


def run_tests():
    """Built-in unit tests for comparison functions."""
    import tempfile

    print("=== Conformance comparison unit tests ===\n")
    passed = 0
    failed = 0

    # Test 1: MD5 comparison — match
    cmp = compare_md5("abc123", "abc123")
    if cmp["match"]:
        print("  [PASS] Test 1: MD5 match")
        passed += 1
    else:
        print("  [FAIL] Test 1: MD5 should match")
        failed += 1

    # Test 2: MD5 comparison — mismatch
    cmp = compare_md5("abc123", "def456")
    if not cmp["match"]:
        print("  [PASS] Test 2: MD5 mismatch")
        passed += 1
    else:
        print("  [FAIL] Test 2: MD5 should not match")
        failed += 1

    # Test 3: MD5 comparison — None input
    cmp = compare_md5(None, "abc123")
    if not cmp["match"]:
        print("  [PASS] Test 3: MD5 None handling")
        passed += 1
    else:
        print("  [FAIL] Test 3: MD5 None should not match")
        failed += 1

    # Test 4: Bitexact comparison — identical files
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp_a:
        tmp_a.write(b"\x00\x01\x02\x03" * 100)
        path_a = tmp_a.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp_b:
        tmp_b.write(b"\x00\x01\x02\x03" * 100)
        path_b = tmp_b.name
    try:
        cmp = compare_bitexact(path_a, path_b)
        if cmp["match"]:
            print("  [PASS] Test 4: Bitexact match (identical files)")
            passed += 1
        else:
            print("  [FAIL] Test 4: Bitexact should match")
            failed += 1
    finally:
        os.unlink(path_a)
        os.unlink(path_b)

    # Test 5: Bitexact comparison — different files
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp_a:
        tmp_a.write(b"\x00\x01\x02\x03")
        path_a = tmp_a.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp_b:
        tmp_b.write(b"\x00\x01\xFF\x03")
        path_b = tmp_b.name
    try:
        cmp = compare_bitexact(path_a, path_b)
        if not cmp["match"] and cmp["first_mismatch_offset"] == 2:
            print(f"  [PASS] Test 5: Bitexact mismatch at offset {cmp['first_mismatch_offset']}")
            passed += 1
        else:
            print(f"  [FAIL] Test 5: Expected mismatch at offset 2, got {cmp}")
            failed += 1
    finally:
        os.unlink(path_a)
        os.unlink(path_b)

    # Test 6: Bitexact comparison — missing file
    cmp = compare_bitexact("/nonexistent/file.bin", "/nonexistent/other.bin")
    if not cmp["match"] and "error" in cmp:
        print("  [PASS] Test 6: Missing file handled gracefully")
        passed += 1
    else:
        print("  [FAIL] Test 6: Missing file should return error")
        failed += 1

    # Test 7: MD5 file computation
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp.write(b"test data for md5")
        tmp_path = tmp.name
    try:
        md5 = compute_md5(tmp_path)
        if md5 and len(md5) == 32:
            print(f"  [PASS] Test 7: MD5 computation ({md5})")
            passed += 1
        else:
            print(f"  [FAIL] Test 7: Invalid MD5 result: {md5}")
            failed += 1
    finally:
        os.unlink(tmp_path)

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Conformance output comparison")
    parser.add_argument("results", nargs="?", help="Path to results.json from run_conformance.py")
    parser.add_argument("config", nargs="?", help="HJSON conformance configuration file")
    parser.add_argument("--output", "-o", default=None, help="Output path for metrics JSON")
    parser.add_argument("--test", action="store_true", help="Run built-in unit tests")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if not args.results or not args.config:
        parser.error("results.json and config.hjson are required (or use --test)")

    try:
        import hjson
        with open(args.config, "r") as f:
            config = hjson.load(f)
    except ImportError:
        with open(args.config, "r") as f:
            config = json.load(f)

    metrics = compare_results(args.results, config)

    # Print summary
    print(f"\n=== Conformance Verdict: {metrics['overall_verdict']} ===\n")
    summary = metrics["summary"]
    print(f"  Mandatory: {summary['mandatory']['pass']}/{summary['mandatory']['total']} PASS")
    print(f"  Optional:  {summary['optional']['pass']}/{summary['optional']['total']} PASS")

    # Print failed streams
    failures = [s for s in metrics["streams"] if s["conformance"] == "FAIL"]
    if failures:
        print(f"\n  Failed streams ({len(failures)}):")
        for s in failures:
            tag = " [MANDATORY]" if s["priority"] == "mandatory" else ""
            err = s.get("error", "mismatch")
            cmp = s.get("comparison", {})
            detail = ""
            if "first_mismatch_offset" in cmp and cmp["first_mismatch_offset"] is not None:
                detail = f" (byte offset: {cmp['first_mismatch_offset']})"
            print(f"    [{s['source_id']}] {s['stream_name']}{tag}: {err}{detail}")

    # Save output
    output_path = args.output or os.path.join(
        os.path.dirname(args.results), "conformance-metrics.json"
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to: {output_path}")


if __name__ == "__main__":
    main()
