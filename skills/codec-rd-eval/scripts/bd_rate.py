#!/usr/bin/env python3
"""bd_rate.py — BD-PSNR and BD-rate calculation using VCEG-M33 methodology.

Computes Bjontegaard Delta metrics from RD (Rate-Distortion) data points.
Supports 3+ point polynomial interpolation in log-rate domain (standard: 4 points).

Reference: ITU-T VCEG-M33 (T. Bjontegaard, "Calculation of average PSNR
differences between RD-curves", April 2001)

Usage:
    python3 bd_rate.py <results.json> [--output <bd-metrics.json>]
    python3 bd_rate.py --test  # Run built-in unit tests

Dependencies: numpy
"""

import argparse
import json
import os
import sys
import warnings
from typing import Optional

import numpy as np


def _validate_inputs(anchor_rates, anchor_psnrs, test_rates, test_psnrs):
    """Validate RD point inputs for BD metric calculation.

    Raises:
        ValueError: If inputs are invalid (too few points, non-positive values).
    """
    n_anchor = len(anchor_rates)
    n_test = len(test_rates)
    if n_anchor < 3:
        raise ValueError(f"BD-rate requires at least 3 anchor RD points, got {n_anchor}")
    if n_test < 3:
        raise ValueError(f"BD-rate requires at least 3 test RD points, got {n_test}")
    if n_anchor != len(anchor_psnrs):
        raise ValueError(f"Anchor rates ({n_anchor}) and PSNRs ({len(anchor_psnrs)}) length mismatch")
    if n_test != len(test_psnrs):
        raise ValueError(f"Test rates ({n_test}) and PSNRs ({len(test_psnrs)}) length mismatch")

    # Guard against log10(0) — all rates must be positive
    if any(r <= 0 for r in anchor_rates) or any(r <= 0 for r in test_rates):
        raise ValueError(
            f"All rates must be positive for log10 transform. "
            f"Anchor rates: {list(anchor_rates)}, Test rates: {list(test_rates)}")
    if any(p <= 0 for p in anchor_psnrs) or any(p <= 0 for p in test_psnrs):
        raise ValueError(
            f"All PSNR values must be positive. "
            f"Anchor PSNR: {list(anchor_psnrs)}, Test PSNR: {list(test_psnrs)}")


def _poly_degree(n_points: int) -> int:
    """Determine polynomial degree for fitting.

    Standard VCEG-M33 uses degree 3 with 4 points (exact fit).
    For N>4 points: degree 3 (least-squares fit).
    For 3 points: degree 2 (quadratic fallback).
    """
    deg = min(3, n_points - 1)
    if n_points != 4:
        warnings.warn(
            f"BD-rate standard (VCEG-M33) uses exactly 4 points. "
            f"Got {n_points} points, using degree-{deg} polynomial fit.",
            stacklevel=3,
        )
    return deg


def _integrate_poly(poly_coeffs, lo, hi):
    """Definite integral of polynomial from lo to hi.

    Supports degree 2 (3 coeffs) or degree 3 (4 coeffs).
    """
    n = len(poly_coeffs)
    # Polynomial: c[0]*x^(n-1) + c[1]*x^(n-2) + ... + c[n-1]
    # Integral:   c[0]/(n)*x^n + c[1]/(n-1)*x^(n-1) + ... + c[n-1]*x
    def F(x):
        val = 0.0
        for i, c in enumerate(poly_coeffs):
            power = n - i  # exponent after integration
            val += c / power * x**power
        return val
    return F(hi) - F(lo)


def bd_rate(anchor_rates: list, anchor_psnrs: list,
            test_rates: list, test_psnrs: list) -> float:
    """Calculate BD-rate (%) using VCEG-M33 methodology.

    Negative BD-rate means the test is better (lower bitrate for same quality).

    Args:
        anchor_rates: Anchor bitrates (3+ points, ascending order)
        anchor_psnrs: Anchor PSNR values (corresponding to rates)
        test_rates: Test bitrates (3+ points, ascending order)
        test_psnrs: Test PSNR values (corresponding to rates)

    Returns:
        BD-rate as percentage. Negative = test is better.

    Raises:
        ValueError: If fewer than 3 points or non-positive values.
    """
    _validate_inputs(anchor_rates, anchor_psnrs, test_rates, test_psnrs)

    # Transform rates to log10 domain
    log_anchor_rates = np.log10(np.array(anchor_rates, dtype=np.float64))
    log_test_rates = np.log10(np.array(test_rates, dtype=np.float64))
    anchor_psnrs_arr = np.array(anchor_psnrs, dtype=np.float64)
    test_psnrs_arr = np.array(test_psnrs, dtype=np.float64)

    deg_a = _poly_degree(len(anchor_rates))
    deg_t = _poly_degree(len(test_rates))

    # Fit polynomial: PSNR → log_rate
    poly_anchor = np.polyfit(anchor_psnrs_arr, log_anchor_rates, deg_a)
    poly_test = np.polyfit(test_psnrs_arr, log_test_rates, deg_t)

    # Common PSNR range for integration
    psnr_min = max(anchor_psnrs_arr.min(), test_psnrs_arr.min())
    psnr_max = min(anchor_psnrs_arr.max(), test_psnrs_arr.max())

    if psnr_min >= psnr_max:
        return 0.0  # No overlapping range

    int_anchor = _integrate_poly(poly_anchor, psnr_min, psnr_max)
    int_test = _integrate_poly(poly_test, psnr_min, psnr_max)

    # BD-rate: average difference in log-rate domain, converted to percentage
    avg_diff = (int_test - int_anchor) / (psnr_max - psnr_min)
    result = (10.0 ** avg_diff - 1.0) * 100.0

    return result


def bd_psnr(anchor_rates: list, anchor_psnrs: list,
            test_rates: list, test_psnrs: list) -> float:
    """Calculate BD-PSNR (dB) using VCEG-M33 methodology.

    Positive BD-PSNR means the test is better (higher PSNR for same bitrate).

    Args:
        anchor_rates: Anchor bitrates (3+ points, ascending order)
        anchor_psnrs: Anchor PSNR values (corresponding to rates)
        test_rates: Test bitrates (3+ points, ascending order)
        test_psnrs: Test PSNR values (corresponding to rates)

    Returns:
        BD-PSNR in dB. Positive = test is better.

    Raises:
        ValueError: If fewer than 3 points or non-positive values.
    """
    _validate_inputs(anchor_rates, anchor_psnrs, test_rates, test_psnrs)

    # Transform rates to log10 domain
    log_anchor_rates = np.log10(np.array(anchor_rates, dtype=np.float64))
    log_test_rates = np.log10(np.array(test_rates, dtype=np.float64))
    anchor_psnrs_arr = np.array(anchor_psnrs, dtype=np.float64)
    test_psnrs_arr = np.array(test_psnrs, dtype=np.float64)

    deg_a = _poly_degree(len(anchor_rates))
    deg_t = _poly_degree(len(test_rates))

    # Fit polynomial: log_rate → PSNR
    poly_anchor = np.polyfit(log_anchor_rates, anchor_psnrs_arr, deg_a)
    poly_test = np.polyfit(log_test_rates, test_psnrs_arr, deg_t)

    # Common log-rate range for integration
    rate_min = max(log_anchor_rates.min(), log_test_rates.min())
    rate_max = min(log_anchor_rates.max(), log_test_rates.max())

    if rate_min >= rate_max:
        return 0.0

    int_anchor = _integrate_poly(poly_anchor, rate_min, rate_max)
    int_test = _integrate_poly(poly_test, rate_min, rate_max)

    # BD-PSNR: average difference in PSNR domain
    result = (int_test - int_anchor) / (rate_max - rate_min)

    return result


def compute_metrics_from_results(results_path: str) -> dict:
    """Compute BD metrics from run_eval.py results file.

    Supports both 2-config (anchor/test) and N-config (candidates[]) modes.
    In N-config mode, computes BD metrics for each test vs the anchor.

    Args:
        results_path: Path to results.json from run_eval.py

    Returns:
        Dictionary with per-sequence and aggregate BD metrics.
        In N-config mode, returns per-comparison results.
    """
    with open(results_path, "r") as f:
        results = json.load(f)

    # Collect all labels from successful results
    labels = list(dict.fromkeys(
        r["config_label"] for r in results if r["status"] == "success"
    ))

    if len(labels) < 2:
        return {"error": "Need at least 2 configurations", "sequences": {}}

    # Identify anchor label
    anchor_label = labels[0]
    for label in labels:
        if any(kw in label.lower() for kw in ["anchor", "baseline", "original", "reference"]):
            anchor_label = label
            break

    test_labels = [l for l in labels if l != anchor_label]

    # Build per-label data: {label: {sequence: [(rate, psnr_y, psnr_yuv, encode_time, ssim, vmaf)]}}
    all_data = {}
    for r in results:
        if r["status"] != "success":
            continue
        label = r["config_label"]
        seq = r["sequence"]
        entry = (
            r["bitrate_kbps"], r["psnr_y"], r["psnr_yuv"], r.get("encode_time_s", 0),
            r.get("ssim"), r.get("vmaf"),
        )
        all_data.setdefault(label, {}).setdefault(seq, []).append(entry)

    anchor_data = all_data.get(anchor_label, {})

    # Compute BD metrics for each test vs anchor
    comparisons = []

    for test_label in test_labels:
        test_data = all_data.get(test_label, {})
        comp = _compute_one_comparison(anchor_label, anchor_data, test_label, test_data)
        comparisons.append(comp)

    # If only one comparison, return flat format for backward compatibility
    if len(comparisons) == 1:
        return comparisons[0]

    # N-config: return all comparisons
    return {
        "anchor_label": anchor_label,
        "comparisons": comparisons,
        "num_comparisons": len(comparisons),
    }


def _compute_one_comparison(anchor_label, anchor_data, test_label, test_data) -> dict:
    """Compute BD metrics for one anchor vs test pair."""
    metrics = {
        "anchor_label": anchor_label,
        "test_label": test_label,
        "sequences": {},
        "aggregate": {},
    }

    bd_rates_y = []
    bd_psnrs_y = []
    bd_rates_yuv = []
    bd_psnrs_yuv = []
    avg_encode_times = {"anchor": [], "test": []}

    common_seqs = sorted(set(anchor_data.keys()) & set(test_data.keys()))

    for seq in common_seqs:
        anchor_pts = sorted(anchor_data[seq], key=lambda x: x[0])
        test_pts = sorted(test_data[seq], key=lambda x: x[0])

        if len(anchor_pts) < 3 or len(test_pts) < 3:
            metrics["sequences"][seq] = {
                "error": f"Insufficient RD points (anchor={len(anchor_pts)}, test={len(test_pts)})",
            }
            continue

        a_rates = [p[0] for p in anchor_pts]
        a_psnr_y = [p[1] for p in anchor_pts]
        a_psnr_yuv = [p[2] for p in anchor_pts]
        t_rates = [p[0] for p in test_pts]
        t_psnr_y = [p[1] for p in test_pts]
        t_psnr_yuv = [p[2] for p in test_pts]

        # Encoding time averages
        a_times = [p[3] for p in anchor_pts if p[3] > 0]
        t_times = [p[3] for p in test_pts if p[3] > 0]
        if a_times:
            avg_encode_times["anchor"].append(sum(a_times) / len(a_times))
        if t_times:
            avg_encode_times["test"].append(sum(t_times) / len(t_times))

        seq_metrics = {
            "anchor_rd": [{"rate": r, "psnr_y": py, "psnr_yuv": pyuv}
                          for r, py, pyuv, *_ in anchor_pts],
            "test_rd": [{"rate": r, "psnr_y": py, "psnr_yuv": pyuv}
                        for r, py, pyuv, *_ in test_pts],
            "num_anchor_points": len(anchor_pts),
            "num_test_points": len(test_pts),
        }

        # Add SSIM/VMAF data if available
        a_ssim = [p[4] for p in anchor_pts if p[4] is not None]
        t_ssim = [p[4] for p in test_pts if p[4] is not None]
        if a_ssim:
            seq_metrics["anchor_avg_ssim"] = round(sum(a_ssim) / len(a_ssim), 6)
        if t_ssim:
            seq_metrics["test_avg_ssim"] = round(sum(t_ssim) / len(t_ssim), 6)

        a_vmaf = [p[5] for p in anchor_pts if p[5] is not None]
        t_vmaf = [p[5] for p in test_pts if p[5] is not None]
        if a_vmaf:
            seq_metrics["anchor_avg_vmaf"] = round(sum(a_vmaf) / len(a_vmaf), 2)
        if t_vmaf:
            seq_metrics["test_avg_vmaf"] = round(sum(t_vmaf) / len(t_vmaf), 2)

        try:
            seq_metrics["bd_rate_y"] = round(bd_rate(a_rates, a_psnr_y, t_rates, t_psnr_y), 4)
            seq_metrics["bd_psnr_y"] = round(bd_psnr(a_rates, a_psnr_y, t_rates, t_psnr_y), 4)
            seq_metrics["bd_rate_yuv"] = round(bd_rate(a_rates, a_psnr_yuv, t_rates, t_psnr_yuv), 4)
            seq_metrics["bd_psnr_yuv"] = round(bd_psnr(a_rates, a_psnr_yuv, t_rates, t_psnr_yuv), 4)

            bd_rates_y.append(seq_metrics["bd_rate_y"])
            bd_psnrs_y.append(seq_metrics["bd_psnr_y"])
            bd_rates_yuv.append(seq_metrics["bd_rate_yuv"])
            bd_psnrs_yuv.append(seq_metrics["bd_psnr_yuv"])
        except (ValueError, np.linalg.LinAlgError) as e:
            seq_metrics["error"] = str(e)

        metrics["sequences"][seq] = seq_metrics

    # Aggregate (simple average)
    if bd_rates_y:
        metrics["aggregate"] = {
            "avg_bd_rate_y": round(sum(bd_rates_y) / len(bd_rates_y), 4),
            "avg_bd_psnr_y": round(sum(bd_psnrs_y) / len(bd_psnrs_y), 4),
            "avg_bd_rate_yuv": round(sum(bd_rates_yuv) / len(bd_rates_yuv), 4),
            "avg_bd_psnr_yuv": round(sum(bd_psnrs_yuv) / len(bd_psnrs_yuv), 4),
            "num_sequences": len(bd_rates_y),
        }

        # Add encoding time summary
        if avg_encode_times["anchor"]:
            metrics["aggregate"]["avg_anchor_encode_time_s"] = round(
                sum(avg_encode_times["anchor"]) / len(avg_encode_times["anchor"]), 2)
        if avg_encode_times["test"]:
            metrics["aggregate"]["avg_test_encode_time_s"] = round(
                sum(avg_encode_times["test"]) / len(avg_encode_times["test"]), 2)

    return metrics


def run_tests():
    """Built-in unit tests for BD-rate/BD-PSNR calculation."""
    print("=== BD-rate/BD-PSNR unit tests ===\n")
    passed = 0
    failed = 0

    # Suppress expected warnings during tests
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Test 1: Identical curves → BD-rate = 0, BD-PSNR = 0
        rates = [100, 200, 400, 800]
        psnrs = [30.0, 33.0, 36.0, 39.0]
        br = bd_rate(rates, psnrs, rates, psnrs)
        bp = bd_psnr(rates, psnrs, rates, psnrs)
        if abs(br) < 0.01 and abs(bp) < 0.01:
            print("  [PASS] Test 1: Identical curves -> BD-rate ~ 0, BD-PSNR ~ 0")
            passed += 1
        else:
            print(f"  [FAIL] Test 1: Expected ~0, got BD-rate={br:.4f}%, BD-PSNR={bp:.4f}dB")
            failed += 1

        # Test 2: Test has better quality at same rates → positive BD-PSNR
        anchor_rates = [100, 200, 400, 800]
        anchor_psnrs = [30.0, 33.0, 36.0, 39.0]
        test_rates = [100, 200, 400, 800]
        test_psnrs = [31.0, 34.0, 37.0, 40.0]
        bp = bd_psnr(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
        if bp > 0.5:
            print(f"  [PASS] Test 2: Better test quality -> BD-PSNR = {bp:.4f} dB (positive)")
            passed += 1
        else:
            print(f"  [FAIL] Test 2: Expected positive BD-PSNR, got {bp:.4f} dB")
            failed += 1

        # Test 3: Test uses less bitrate at same quality → negative BD-rate
        anchor_rates = [200, 400, 800, 1600]
        anchor_psnrs = [30.0, 33.0, 36.0, 39.0]
        test_rates = [150, 300, 600, 1200]
        test_psnrs = [30.0, 33.0, 36.0, 39.0]
        br = bd_rate(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
        if br < -10:
            print(f"  [PASS] Test 3: Lower test bitrate -> BD-rate = {br:.4f}% (negative)")
            passed += 1
        else:
            print(f"  [FAIL] Test 3: Expected negative BD-rate (< -10%), got {br:.4f}%")
            failed += 1

        # Test 4: Test is worse → positive BD-rate, negative BD-PSNR
        anchor_rates = [100, 200, 400, 800]
        anchor_psnrs = [32.0, 35.0, 38.0, 41.0]
        test_rates = [150, 300, 600, 1200]
        test_psnrs = [32.0, 35.0, 38.0, 41.0]
        br = bd_rate(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
        if br > 10:
            print(f"  [PASS] Test 4: Worse test -> BD-rate = {br:.4f}% (positive)")
            passed += 1
        else:
            print(f"  [FAIL] Test 4: Expected positive BD-rate (> 10%), got {br:.4f}%")
            failed += 1

        # Test 5: Known reference values (realistic H.264 data)
        anchor_rates_5 = [512.0, 1024.0, 2048.0, 4096.0]
        anchor_psnrs_5 = [33.5, 36.8, 39.9, 42.5]
        test_rates_5 = [480.0, 960.0, 1920.0, 3840.0]
        test_psnrs_5 = [33.7, 37.0, 40.1, 42.7]
        br5 = bd_rate(anchor_rates_5, anchor_psnrs_5, test_rates_5, test_psnrs_5)
        bp5 = bd_psnr(anchor_rates_5, anchor_psnrs_5, test_rates_5, test_psnrs_5)
        if br5 < 0 and bp5 > 0:
            print(f"  [PASS] Test 5: Realistic data -> BD-rate={br5:.2f}%, BD-PSNR={bp5:.4f}dB")
            passed += 1
        else:
            print(f"  [FAIL] Test 5: Expected negative BD-rate and positive BD-PSNR, got {br5:.2f}%, {bp5:.4f}dB")
            failed += 1

        # Test 6: log10(0) guard — should raise ValueError
        try:
            bd_rate([0, 200, 400, 800], [30, 33, 36, 39],
                    [100, 200, 400, 800], [30, 33, 36, 39])
            print("  [FAIL] Test 6: Expected ValueError for rate=0, but no exception raised")
            failed += 1
        except ValueError:
            print("  [PASS] Test 6: log10(0) guard raises ValueError")
            passed += 1

        # Test 7: 5-point BD-rate (least-squares fit, should still work)
        rates_5pt = [100, 200, 400, 800, 1600]
        psnrs_5pt = [28.0, 31.0, 34.0, 37.0, 39.5]
        test_5pt = [90, 180, 360, 720, 1440]
        tpsnrs_5pt = [28.0, 31.0, 34.0, 37.0, 39.5]
        br7 = bd_rate(rates_5pt, psnrs_5pt, test_5pt, tpsnrs_5pt)
        if br7 < -5:
            print(f"  [PASS] Test 7: 5-point BD-rate = {br7:.4f}% (negative, as expected)")
            passed += 1
        else:
            print(f"  [FAIL] Test 7: 5-point, expected negative BD-rate, got {br7:.4f}%")
            failed += 1

        # Test 8: 3-point BD-rate (quadratic fallback)
        rates_3pt = [200, 400, 800]
        psnrs_3pt = [31.0, 34.0, 37.0]
        test_3pt = [150, 300, 600]
        tpsnrs_3pt = [31.0, 34.0, 37.0]
        br8 = bd_rate(rates_3pt, psnrs_3pt, test_3pt, tpsnrs_3pt)
        if br8 < -10:
            print(f"  [PASS] Test 8: 3-point BD-rate = {br8:.4f}% (quadratic fallback)")
            passed += 1
        else:
            print(f"  [FAIL] Test 8: 3-point, expected negative BD-rate, got {br8:.4f}%")
            failed += 1

        # Test 9: <3 points should raise ValueError
        try:
            bd_rate([100, 200], [30, 33], [100, 200], [30, 33])
            print("  [FAIL] Test 9: Expected ValueError for 2 points, but no exception raised")
            failed += 1
        except ValueError:
            print("  [PASS] Test 9: <3 points raises ValueError")
            passed += 1

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="BD-PSNR/BD-rate calculator (VCEG-M33)")
    parser.add_argument("results", nargs="?", help="Path to results.json from run_eval.py")
    parser.add_argument("--output", "-o", default=None,
                        help="Output path for BD metrics JSON")
    parser.add_argument("--test", action="store_true",
                        help="Run built-in unit tests")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if not args.results:
        parser.error("results.json path is required (or use --test)")

    metrics = compute_metrics_from_results(args.results)

    # Print summary
    if "comparisons" in metrics:
        # N-config mode
        print(f"\n=== BD Metrics: {metrics['num_comparisons']} comparisons vs {metrics['anchor_label']} ===\n")
        for comp in metrics["comparisons"]:
            _print_comparison(comp)
    else:
        # Single comparison mode
        _print_comparison(metrics)

    # Save output
    output_path = args.output or (
        os.path.join(os.path.dirname(args.results), "bd-metrics.json")
        if args.results else "bd-metrics.json"
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to: {output_path}")


def _print_comparison(comp: dict):
    """Pretty-print one anchor vs test comparison."""
    anchor = comp.get("anchor_label", "?")
    test = comp.get("test_label", "?")
    print(f"--- {anchor} vs {test} ---\n")

    for seq, data in comp.get("sequences", {}).items():
        if "error" in data:
            print(f"  {seq}: ERROR - {data['error']}")
        else:
            pts_info = f" ({data.get('num_anchor_points', '?')}/{data.get('num_test_points', '?')} pts)"
            print(f"  {seq}{pts_info}:")
            print(f"    BD-rate (Y):   {data['bd_rate_y']:+.2f}%")
            print(f"    BD-PSNR (Y):   {data['bd_psnr_y']:+.4f} dB")
            print(f"    BD-rate (YUV): {data['bd_rate_yuv']:+.2f}%")
            print(f"    BD-PSNR (YUV): {data['bd_psnr_yuv']:+.4f} dB")
            if "test_avg_ssim" in data:
                print(f"    SSIM (avg):    {data['test_avg_ssim']:.6f}")
            if "test_avg_vmaf" in data:
                print(f"    VMAF (avg):    {data['test_avg_vmaf']:.2f}")

    agg = comp.get("aggregate", {})
    if agg:
        print(f"\n  --- Average ({agg['num_sequences']} sequences) ---")
        print(f"    BD-rate (Y):   {agg['avg_bd_rate_y']:+.2f}%")
        print(f"    BD-PSNR (Y):   {agg['avg_bd_psnr_y']:+.4f} dB")
        print(f"    BD-rate (YUV): {agg['avg_bd_rate_yuv']:+.2f}%")
        print(f"    BD-PSNR (YUV): {agg['avg_bd_psnr_yuv']:+.4f} dB")
        if "avg_anchor_encode_time_s" in agg:
            print(f"    Anchor avg encode time: {agg['avg_anchor_encode_time_s']:.2f}s")
        if "avg_test_encode_time_s" in agg:
            print(f"    Test avg encode time:   {agg['avg_test_encode_time_s']:.2f}s")
    print()


if __name__ == "__main__":
    main()
