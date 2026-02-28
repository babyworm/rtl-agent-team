#!/usr/bin/env python3
"""run_eval.py — Parallel encoding simulation orchestrator for codec RD evaluation.

Parses HJSON test configuration, runs encoder across all (sequence, QP, config)
combinations in parallel, and collects bitrate + PSNR results.

Usage:
    python3 run_eval.py <config.hjson> --mode local [--max-parallel N]
    python3 run_eval.py <config.hjson> --mode aws-batch

Dependencies: hjson, numpy (for result aggregation)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class EncodingResult:
    """Result of a single encoding run."""
    sequence: str
    qp: int
    config_label: str
    bitrate_kbps: float
    psnr_y: float
    psnr_u: float
    psnr_v: float
    psnr_yuv: float
    encode_time_s: float
    status: str  # "success" | "failed"
    error: Optional[str] = None


def load_config(config_path: str) -> dict:
    """Load HJSON test configuration."""
    try:
        import hjson
    except ImportError:
        print("ERROR: hjson package not installed. Run: pip install hjson", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        return hjson.load(f)


def parse_encoder_output(stdout: str, stderr: str) -> dict:
    """Parse encoder stdout/stderr for bitrate and PSNR values.

    Supports common encoder output formats. Patterns can be extended
    for specific encoder implementations.
    """
    result = {
        "bitrate_kbps": 0.0,
        "psnr_y": 0.0,
        "psnr_u": 0.0,
        "psnr_v": 0.0,
        "psnr_yuv": 0.0,
    }

    combined = stdout + "\n" + stderr

    # Pattern: "Bitrate: 1234.56 kbps" or "bitrate=1234.56"
    m = re.search(r'[Bb]itrate[:\s=]+([0-9.]+)\s*(?:kbps|kb/s)?', combined)
    if m:
        result["bitrate_kbps"] = float(m.group(1))

    # Pattern: "PSNR Y: 38.12 U: 40.34 V: 41.56" or "PSNR-Y=38.12"
    m = re.search(r'PSNR[\s-]*Y[:\s=]+([0-9.]+)', combined)
    if m:
        result["psnr_y"] = float(m.group(1))
    m = re.search(r'PSNR[\s-]*U[:\s=]+([0-9.]+)', combined)
    if m:
        result["psnr_u"] = float(m.group(1))
    m = re.search(r'PSNR[\s-]*V[:\s=]+([0-9.]+)', combined)
    if m:
        result["psnr_v"] = float(m.group(1))

    # YUV combined PSNR (6:1:1 weighting if not explicitly provided)
    m = re.search(r'PSNR[\s-]*(?:YUV|All)[:\s=]+([0-9.]+)', combined)
    if m:
        result["psnr_yuv"] = float(m.group(1))
    elif result["psnr_y"] > 0:
        # Standard 6:1:1 weighting for 4:2:0
        result["psnr_yuv"] = (
            6 * result["psnr_y"] + result["psnr_u"] + result["psnr_v"]
        ) / 8.0

    return result


def run_single_encode(
    encoder_binary: str,
    encoder_cfg: str,
    sequence: dict,
    qp: int,
    config_label: str,
    output_dir: str,
    timeout: int,
) -> EncodingResult:
    """Run a single encoding job."""
    seq_name = sequence["name"]
    output_bitstream = os.path.join(output_dir, f"{seq_name}_qp{qp}_{config_label}.bin")
    output_recon = os.path.join(output_dir, f"{seq_name}_qp{qp}_{config_label}_rec.yuv")

    cmd = [
        encoder_binary,
        "-c", encoder_cfg,
        "-i", sequence["path"],
        "-wdt", str(sequence["width"]),
        "-hgt", str(sequence["height"]),
        "-fr", str(sequence.get("fps", 30)),
        "-f", str(sequence.get("frames", 100)),
        "-q", str(qp),
        "-b", output_bitstream,
        "-o", output_recon,
    ]

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start

        if proc.returncode != 0:
            return EncodingResult(
                sequence=seq_name,
                qp=qp,
                config_label=config_label,
                bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
                encode_time_s=elapsed,
                status="failed",
                error=f"Exit code {proc.returncode}: {proc.stderr[:500]}",
            )

        metrics = parse_encoder_output(proc.stdout, proc.stderr)
        return EncodingResult(
            sequence=seq_name,
            qp=qp,
            config_label=config_label,
            bitrate_kbps=metrics["bitrate_kbps"],
            psnr_y=metrics["psnr_y"],
            psnr_u=metrics["psnr_u"],
            psnr_v=metrics["psnr_v"],
            psnr_yuv=metrics["psnr_yuv"],
            encode_time_s=elapsed,
            status="success",
        )

    except subprocess.TimeoutExpired:
        return EncodingResult(
            sequence=seq_name,
            qp=qp,
            config_label=config_label,
            bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
            encode_time_s=timeout,
            status="failed",
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return EncodingResult(
            sequence=seq_name,
            qp=qp,
            config_label=config_label,
            bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
            encode_time_s=time.time() - start,
            status="failed",
            error=str(e),
        )


def run_local(config: dict, output_dir: str) -> list:
    """Run all encoding jobs locally in parallel."""
    max_parallel = config.get("execution", {}).get("max_parallel", os.cpu_count() or 4)
    timeout = config.get("execution", {}).get("timeout_per_job", 3600)
    sequences = config["sequences"]
    qp_points = config["qp_points"]

    # Build job list for both anchor and test
    jobs = []
    for cfg_key in ["anchor", "test"]:
        cfg = config[cfg_key]
        encoder_binary = cfg.get("encoder_binary", "")
        encoder_cfg = cfg.get("encoder_cfg", "")
        label = cfg.get("label", cfg_key)

        for seq in sequences:
            for qp in qp_points:
                jobs.append((encoder_binary, encoder_cfg, seq, qp, label, output_dir, timeout))

    total = len(jobs)
    results = []
    completed = 0

    print(f"Running {total} encoding jobs (max {max_parallel} parallel)...")

    with ProcessPoolExecutor(max_workers=max_parallel) as executor:
        futures = {
            executor.submit(run_single_encode, *job): job
            for job in jobs
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1

            status_icon = "OK" if result.status == "success" else "FAIL"
            print(f"  [{completed}/{total}] {status_icon} {result.config_label} / "
                  f"{result.sequence} / QP={result.qp} "
                  f"({result.encode_time_s:.1f}s)")

    return results


def run_aws_batch(config: dict, output_dir: str) -> list:
    """Submit encoding jobs to AWS Batch (placeholder for aws_batch_submit.py)."""
    print("AWS Batch mode: delegating to aws_batch_submit.py...")
    aws_script = os.path.join(os.path.dirname(__file__), "aws_batch_submit.py")

    # Save config for AWS batch script
    config_path = os.path.join(output_dir, "eval_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    proc = subprocess.run(
        [sys.executable, aws_script, config_path, "--output-dir", output_dir],
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        print(f"ERROR: AWS Batch submission failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

    # Load results from AWS batch output
    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "r") as f:
        raw = json.load(f)
    return [EncodingResult(**r) for r in raw]


def main():
    parser = argparse.ArgumentParser(description="Codec RD evaluation orchestrator")
    parser.add_argument("config", help="HJSON test configuration file")
    parser.add_argument("--mode", choices=["local", "aws-batch"], default="local",
                        help="Execution mode (default: local)")
    parser.add_argument("--max-parallel", type=int, default=None,
                        help="Override max parallel jobs (local mode)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for results")
    args = parser.parse_args()

    config = load_config(args.config)

    # Determine output directory
    output_dir = args.output_dir or config.get("output", {}).get(
        "raw_data_path", ".rtl-agent-team/scratch/rd-eval"
    )
    os.makedirs(output_dir, exist_ok=True)

    if args.max_parallel and "execution" in config:
        config["execution"]["max_parallel"] = args.max_parallel

    # Run encoding
    if args.mode == "local":
        results = run_local(config, output_dir)
    else:
        results = run_aws_batch(config, output_dir)

    # Summary
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    print(f"\n=== Evaluation complete: {success} succeeded, {failed} failed ===")

    if failed > 0:
        print("\nFailed jobs:")
        for r in results:
            if r.status == "failed":
                print(f"  {r.config_label} / {r.sequence} / QP={r.qp}: {r.error}")

    # Save results
    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
