#!/usr/bin/env python3
"""bd_rate.py — BD-PSNR and BD-rate calculation using VCEG-M33 methodology.

Computes Bjontegaard Delta metrics from RD (Rate-Distortion) data points.
Uses 4-point 3rd-order polynomial interpolation in log-rate domain.

Reference: ITU-T VCEG-M33 (T. Bjontegaard, "Calculation of average PSNR
differences between RD-curves", April 2001)

Usage:
    python3 bd_rate.py <results.json> [--output <bd-metrics.json>]
    python3 bd_rate.py --test  # Run built-in unit tests

Dependencies: numpy
"""

import argparse
import json
import math
import sys
from typing import Optional

import numpy as np


def bd_rate(anchor_rates: list, anchor_psnrs: list,
            test_rates: list, test_psnrs: list) -> float:
    """Calculate BD-rate (%) using VCEG-M33 methodology.

    Negative BD-rate means the test is better (lower bitrate for same quality).

    Args:
        anchor_rates: Anchor bitrates (4 points, ascending order)
        anchor_psnrs: Anchor PSNR values (4 points, corresponding to rates)
        test_rates: Test bitrates (4 points, ascending order)
        test_psnrs: Test PSNR values (4 points, corresponding to rates)

    Returns:
        BD-rate as percentage. Negative = test is better.
    """
    assert len(anchor_rates) == len(anchor_psnrs) == 4, "Exactly 4 RD points required"
    assert len(test_rates) == len(test_psnrs) == 4, "Exactly 4 RD points required"

    # Transform rates to log10 domain
    log_anchor_rates = np.log10(np.array(anchor_rates, dtype=np.float64))
    log_test_rates = np.log10(np.array(test_rates, dtype=np.float64))
    anchor_psnrs = np.array(anchor_psnrs, dtype=np.float64)
    test_psnrs = np.array(test_psnrs, dtype=np.float64)

    # Fit 3rd-order polynomial: PSNR → log_rate
    poly_anchor = np.polyfit(anchor_psnrs, log_anchor_rates, 3)
    poly_test = np.polyfit(test_psnrs, log_test_rates, 3)

    # Common PSNR range for integration
    psnr_min = max(anchor_psnrs.min(), test_psnrs.min())
    psnr_max = min(anchor_psnrs.max(), test_psnrs.max())

    if psnr_min >= psnr_max:
        return 0.0  # No overlapping range

    # Integrate polynomials over common PSNR range
    # Integral of ax^3 + bx^2 + cx + d = a/4*x^4 + b/3*x^3 + c/2*x^2 + d*x
    def _integrate_poly(poly_coeffs, lo, hi):
        """Definite integral of 3rd-order polynomial from lo to hi."""
        a, b, c, d = poly_coeffs
        def F(x):
            return a / 4 * x**4 + b / 3 * x**3 + c / 2 * x**2 + d * x
        return F(hi) - F(lo)

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
        anchor_rates: Anchor bitrates (4 points, ascending order)
        anchor_psnrs: Anchor PSNR values (4 points, corresponding to rates)
        test_rates: Test bitrates (4 points, ascending order)
        test_psnrs: Test PSNR values (4 points, corresponding to rates)

    Returns:
        BD-PSNR in dB. Positive = test is better.
    """
    assert len(anchor_rates) == len(anchor_psnrs) == 4, "Exactly 4 RD points required"
    assert len(test_rates) == len(test_psnrs) == 4, "Exactly 4 RD points required"

    # Transform rates to log10 domain
    log_anchor_rates = np.log10(np.array(anchor_rates, dtype=np.float64))
    log_test_rates = np.log10(np.array(test_rates, dtype=np.float64))
    anchor_psnrs = np.array(anchor_psnrs, dtype=np.float64)
    test_psnrs = np.array(test_psnrs, dtype=np.float64)

    # Fit 3rd-order polynomial: log_rate → PSNR
    poly_anchor = np.polyfit(log_anchor_rates, anchor_psnrs, 3)
    poly_test = np.polyfit(log_test_rates, test_psnrs, 3)

    # Common log-rate range for integration
    rate_min = max(log_anchor_rates.min(), log_test_rates.min())
    rate_max = min(log_anchor_rates.max(), log_test_rates.max())

    if rate_min >= rate_max:
        return 0.0

    def _integrate_poly(poly_coeffs, lo, hi):
        a, b, c, d = poly_coeffs
        def F(x):
            return a / 4 * x**4 + b / 3 * x**3 + c / 2 * x**2 + d * x
        return F(hi) - F(lo)

    int_anchor = _integrate_poly(poly_anchor, rate_min, rate_max)
    int_test = _integrate_poly(poly_test, rate_min, rate_max)

    # BD-PSNR: average difference in PSNR domain
    result = (int_test - int_anchor) / (rate_max - rate_min)

    return result


def compute_metrics_from_results(results_path: str) -> dict:
    """Compute BD metrics from run_eval.py results file.

    Args:
        results_path: Path to results.json from run_eval.py

    Returns:
        Dictionary with per-sequence and aggregate BD metrics.
    """
    with open(results_path, "r") as f:
        results = json.load(f)

    # Separate anchor and test results
    anchor_data = {}  # {sequence: [(rate, psnr_y, psnr_yuv), ...]}
    test_data = {}

    # Identify anchor and test labels
    labels = set(r["config_label"] for r in results if r["status"] == "success")
    if len(labels) != 2:
        print(f"WARNING: Expected 2 config labels, found {len(labels)}: {labels}",
              file=sys.stderr)
        if len(labels) < 2:
            return {"error": "Need exactly 2 configurations (anchor + test)", "sequences": {}}

    # Heuristic: first label alphabetically or containing "anchor"/"baseline" is anchor
    sorted_labels = sorted(labels)
    anchor_label = sorted_labels[0]
    test_label = sorted_labels[1]
    for label in labels:
        if any(kw in label.lower() for kw in ["anchor", "baseline", "original", "reference"]):
            anchor_label = label
            test_label = [l for l in labels if l != label][0]
            break

    for r in results:
        if r["status"] != "success":
            continue

        seq = r["sequence"]
        entry = (r["bitrate_kbps"], r["psnr_y"], r["psnr_yuv"])

        if r["config_label"] == anchor_label:
            anchor_data.setdefault(seq, []).append(entry)
        else:
            test_data.setdefault(seq, []).append(entry)

    # Compute per-sequence BD metrics
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

    for seq in sorted(set(anchor_data.keys()) & set(test_data.keys())):
        anchor_pts = sorted(anchor_data[seq], key=lambda x: x[0])
        test_pts = sorted(test_data[seq], key=lambda x: x[0])

        if len(anchor_pts) < 4 or len(test_pts) < 4:
            metrics["sequences"][seq] = {
                "error": f"Insufficient RD points (anchor={len(anchor_pts)}, test={len(test_pts)})",
            }
            continue

        # Use first 4 points (standard VCEG-M33 uses exactly 4)
        anchor_pts = anchor_pts[:4]
        test_pts = test_pts[:4]

        a_rates = [p[0] for p in anchor_pts]
        a_psnr_y = [p[1] for p in anchor_pts]
        a_psnr_yuv = [p[2] for p in anchor_pts]
        t_rates = [p[0] for p in test_pts]
        t_psnr_y = [p[1] for p in test_pts]
        t_psnr_yuv = [p[2] for p in test_pts]

        seq_metrics = {
            "anchor_rd": [{"rate": r, "psnr_y": py, "psnr_yuv": pyuv}
                          for r, py, pyuv in anchor_pts],
            "test_rd": [{"rate": r, "psnr_y": py, "psnr_yuv": pyuv}
                        for r, py, pyuv in test_pts],
        }

        try:
            seq_metrics["bd_rate_y"] = round(bd_rate(a_rates, a_psnr_y, t_rates, t_psnr_y), 4)
            seq_metrics["bd_psnr_y"] = round(bd_psnr(a_rates, a_psnr_y, t_rates, t_psnr_y), 4)
            seq_metrics["bd_rate_yuv"] = round(bd_rate(a_rates, a_psnr_yuv, t_rates, t_psnr_yuv), 4)
            seq_metrics["bd_psnr_yuv"] = round(bd_psnr(a_rates, a_psnr_yuv, t_rates, t_psnr_yuv), 4)

            bd_rates_y.append(seq_metrics["bd_rate_y"])
            bd_psnrs_y.append(seq_metrics["bd_psnr_y"])
            bd_rates_yuv.append(seq_metrics["bd_rate_yuv"])
            bd_psnrs_yuv.append(seq_metrics["bd_psnr_yuv"])
        except Exception as e:
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

    return metrics


def run_tests():
    """Built-in unit tests for BD-rate/BD-PSNR calculation."""
    print("=== BD-rate/BD-PSNR unit tests ===\n")
    passed = 0
    failed = 0

    # Test 1: Identical curves → BD-rate = 0, BD-PSNR = 0
    rates = [100, 200, 400, 800]
    psnrs = [30.0, 33.0, 36.0, 39.0]
    br = bd_rate(rates, psnrs, rates, psnrs)
    bp = bd_psnr(rates, psnrs, rates, psnrs)
    if abs(br) < 0.01 and abs(bp) < 0.01:
        print("  [PASS] Test 1: Identical curves → BD-rate ≈ 0, BD-PSNR ≈ 0")
        passed += 1
    else:
        print(f"  [FAIL] Test 1: Expected ~0, got BD-rate={br:.4f}%, BD-PSNR={bp:.4f}dB")
        failed += 1

    # Test 2: Test has better quality at same rates → positive BD-PSNR
    anchor_rates = [100, 200, 400, 800]
    anchor_psnrs = [30.0, 33.0, 36.0, 39.0]
    test_rates = [100, 200, 400, 800]
    test_psnrs = [31.0, 34.0, 37.0, 40.0]  # +1 dB at each point
    bp = bd_psnr(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
    if bp > 0.5:
        print(f"  [PASS] Test 2: Better test quality → BD-PSNR = {bp:.4f} dB (positive)")
        passed += 1
    else:
        print(f"  [FAIL] Test 2: Expected positive BD-PSNR, got {bp:.4f} dB")
        failed += 1

    # Test 3: Test uses less bitrate at same quality → negative BD-rate
    anchor_rates = [200, 400, 800, 1600]
    anchor_psnrs = [30.0, 33.0, 36.0, 39.0]
    test_rates = [150, 300, 600, 1200]  # 25% less bitrate
    test_psnrs = [30.0, 33.0, 36.0, 39.0]
    br = bd_rate(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
    if br < -10:
        print(f"  [PASS] Test 3: Lower test bitrate → BD-rate = {br:.4f}% (negative)")
        passed += 1
    else:
        print(f"  [FAIL] Test 3: Expected negative BD-rate (< -10%), got {br:.4f}%")
        failed += 1

    # Test 4: Test is worse → positive BD-rate, negative BD-PSNR
    anchor_rates = [100, 200, 400, 800]
    anchor_psnrs = [32.0, 35.0, 38.0, 41.0]
    test_rates = [150, 300, 600, 1200]  # 50% more bitrate for same quality
    test_psnrs = [32.0, 35.0, 38.0, 41.0]
    br = bd_rate(anchor_rates, anchor_psnrs, test_rates, test_psnrs)
    if br > 10:
        print(f"  [PASS] Test 4: Worse test → BD-rate = {br:.4f}% (positive)")
        passed += 1
    else:
        print(f"  [FAIL] Test 4: Expected positive BD-rate (> 10%), got {br:.4f}%")
        failed += 1

    # Test 5: Known reference values (approximate, from VCEG-M33 examples)
    # Using realistic RD data from typical H.264 evaluation
    anchor_rates_5 = [512.0, 1024.0, 2048.0, 4096.0]
    anchor_psnrs_5 = [33.5, 36.8, 39.9, 42.5]
    test_rates_5 = [480.0, 960.0, 1920.0, 3840.0]
    test_psnrs_5 = [33.7, 37.0, 40.1, 42.7]
    br5 = bd_rate(anchor_rates_5, anchor_psnrs_5, test_rates_5, test_psnrs_5)
    bp5 = bd_psnr(anchor_rates_5, anchor_psnrs_5, test_rates_5, test_psnrs_5)
    # Test should be better: negative BD-rate, positive BD-PSNR
    if br5 < 0 and bp5 > 0:
        print(f"  [PASS] Test 5: Realistic data → BD-rate={br5:.2f}%, BD-PSNR={bp5:.4f}dB")
        passed += 1
    else:
        print(f"  [FAIL] Test 5: Expected negative BD-rate and positive BD-PSNR, got {br5:.2f}%, {bp5:.4f}dB")
        failed += 1

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
    print(f"\n=== BD Metrics: {metrics.get('anchor_label', '?')} vs {metrics.get('test_label', '?')} ===\n")

    for seq, data in metrics.get("sequences", {}).items():
        if "error" in data:
            print(f"  {seq}: ERROR - {data['error']}")
        else:
            print(f"  {seq}:")
            print(f"    BD-rate (Y):   {data['bd_rate_y']:+.2f}%")
            print(f"    BD-PSNR (Y):   {data['bd_psnr_y']:+.4f} dB")
            print(f"    BD-rate (YUV): {data['bd_rate_yuv']:+.2f}%")
            print(f"    BD-PSNR (YUV): {data['bd_psnr_yuv']:+.4f} dB")

    agg = metrics.get("aggregate", {})
    if agg:
        print(f"\n  --- Average ({agg['num_sequences']} sequences) ---")
        print(f"    BD-rate (Y):   {agg['avg_bd_rate_y']:+.2f}%")
        print(f"    BD-PSNR (Y):   {agg['avg_bd_psnr_y']:+.4f} dB")
        print(f"    BD-rate (YUV): {agg['avg_bd_rate_yuv']:+.2f}%")
        print(f"    BD-PSNR (YUV): {agg['avg_bd_psnr_yuv']:+.4f} dB")

    # Save output
    output_path = args.output or (
        os.path.join(os.path.dirname(args.results), "bd-metrics.json")
        if args.results else "bd-metrics.json"
    )
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to: {output_path}")


if __name__ == "__main__":
    main()
