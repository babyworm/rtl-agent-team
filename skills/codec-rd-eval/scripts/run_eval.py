#!/usr/bin/env python3
"""run_eval.py — Parallel encoding simulation orchestrator for codec RD evaluation.

Parses HJSON test configuration, runs encoder across all (sequence, QP, config)
combinations in parallel, and collects bitrate + PSNR results.

Supports:
- Configurable encoder CLI template (encoder_cmd_template)
- Configurable output parsing patterns (output_parsing)
- N-candidate comparison (candidates[] array)
- SSIM/VMAF opt-in quality metrics
- bit_depth / chroma_format aware YUV weighting

Usage:
    python3 run_eval.py <config.hjson> --mode local [--max-parallel N]
    python3 run_eval.py <config.hjson> --mode aws-batch

Dependencies: hjson, numpy (for result aggregation)
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Default encoder CLI template (HM-style flags)
# ---------------------------------------------------------------------------
DEFAULT_CMD_TEMPLATE = (
    "{encoder} -c {cfg} -i {input} -wdt {width} -hgt {height} "
    "-fr {fps} -f {frames} -q {qp} -b {bitstream} -o {recon}"
)

# ---------------------------------------------------------------------------
# Chroma format → YUV PSNR weighting
# ---------------------------------------------------------------------------
CHROMA_WEIGHTS = {
    "420": (6, 1, 1),   # 6:1:1 (standard 4:2:0)
    "422": (4, 1, 1),   # 4:1:1
    "444": (1, 1, 1),   # equal weight
}


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
    ssim: Optional[float] = None
    vmaf: Optional[float] = None
    is_anchor: bool = False


def sanitize_label(label: str) -> str:
    """Sanitize config label for safe filename usage."""
    sanitized = re.sub(r'[^\w\-.]', '_', label)[:64]
    return sanitized or "unnamed"


def load_config(config_path: str) -> dict:
    """Load HJSON test configuration."""
    try:
        import hjson
    except ImportError:
        print("ERROR: hjson package not installed. Run: pip install hjson", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        return hjson.load(f)


def parse_encoder_output(stdout: str, stderr: str,
                         parsing_config: Optional[dict] = None,
                         chroma_format: str = "420") -> dict:
    """Parse encoder stdout/stderr for bitrate and PSNR values.

    Args:
        stdout: Encoder stdout text.
        stderr: Encoder stderr text.
        parsing_config: Optional dict with custom regex patterns for output parsing.
            Keys: bitrate_pattern, psnr_y_pattern, psnr_u_pattern, psnr_v_pattern,
                  psnr_yuv_pattern, ssim_pattern
        chroma_format: Chroma format string ("420", "422", "444") for YUV weighting.
    """
    result = {
        "bitrate_kbps": 0.0,
        "psnr_y": 0.0,
        "psnr_u": 0.0,
        "psnr_v": 0.0,
        "psnr_yuv": 0.0,
        "ssim": None,
    }

    combined = stdout + "\n" + stderr
    cfg = parsing_config or {}

    # --- Bitrate ---
    pat = cfg.get("bitrate_pattern", r'[Bb]itrate[:\s=]+([0-9.]+)\s*(?:kbps|kb/s)?')
    m = re.search(pat, combined)
    if m:
        result["bitrate_kbps"] = float(m.group(1))

    # --- PSNR Y ---
    pat = cfg.get("psnr_y_pattern", r'PSNR[\s-]*Y[:\s=]+([0-9.]+)')
    m = re.search(pat, combined)
    if m:
        result["psnr_y"] = float(m.group(1))

    # --- PSNR U ---
    pat = cfg.get("psnr_u_pattern", r'PSNR[\s-]*U[:\s=]+([0-9.]+)')
    m = re.search(pat, combined)
    if m:
        result["psnr_u"] = float(m.group(1))

    # --- PSNR V ---
    pat = cfg.get("psnr_v_pattern", r'PSNR[\s-]*V[:\s=]+([0-9.]+)')
    m = re.search(pat, combined)
    if m:
        result["psnr_v"] = float(m.group(1))

    # --- PSNR YUV (explicit or weighted) ---
    pat = cfg.get("psnr_yuv_pattern", r'PSNR[\s-]*(?:YUV|All)[:\s=]+([0-9.]+)')
    m = re.search(pat, combined)
    if m:
        result["psnr_yuv"] = float(m.group(1))
    elif result["psnr_y"] > 0:
        wy, wu, wv = CHROMA_WEIGHTS.get(chroma_format, (6, 1, 1))
        total = wy + wu + wv
        result["psnr_yuv"] = (
            wy * result["psnr_y"] + wu * result["psnr_u"] + wv * result["psnr_v"]
        ) / total

    # --- SSIM (optional, parsed from encoder output) ---
    pat = cfg.get("ssim_pattern", r'SSIM[\s:-]*(?:Y[\s:=]*)?([0-9.]+)')
    m = re.search(pat, combined)
    if m:
        result["ssim"] = float(m.group(1))

    return result


def _run_ffmpeg_ssim(original_yuv: str, recon_yuv: str,
                     width: int, height: int, bit_depth: int = 8) -> Optional[float]:
    """Compute SSIM using ffmpeg (fallback when encoder doesn't output SSIM)."""
    pix_fmt = f"yuv420p{'10le' if bit_depth > 8 else ''}"
    vsize = f"{width}x{height}"
    cmd = [
        "ffmpeg", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", original_yuv,
        "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", recon_yuv,
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


def _run_ffmpeg_vmaf(original_yuv: str, recon_yuv: str,
                     width: int, height: int, bit_depth: int = 8) -> Optional[float]:
    """Compute VMAF using ffmpeg (opt-in quality metric)."""
    pix_fmt = f"yuv420p{'10le' if bit_depth > 8 else ''}"
    vsize = f"{width}x{height}"
    cmd = [
        "ffmpeg", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", recon_yuv,
        "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", vsize, "-i", original_yuv,
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


def run_single_encode(
    encoder_binary: str,
    encoder_cfg: str,
    sequence: dict,
    qp: int,
    config_label: str,
    output_dir: str,
    timeout: int,
    cmd_template: str = DEFAULT_CMD_TEMPLATE,
    parsing_config: Optional[dict] = None,
    quality_metrics: Optional[list] = None,
) -> EncodingResult:
    """Run a single encoding job."""
    seq_name = sequence["name"]
    safe_label = sanitize_label(config_label)
    output_bitstream = os.path.join(output_dir, f"{seq_name}_qp{qp}_{safe_label}.bin")
    output_recon = os.path.join(output_dir, f"{seq_name}_qp{qp}_{safe_label}_rec.yuv")

    bit_depth = sequence.get("bit_depth", 8)
    chroma_format = str(sequence.get("chroma_format", "420"))
    quality_metrics = quality_metrics or ["psnr"]

    # Build command from template
    try:
        cmd_str = cmd_template.format(
            encoder=encoder_binary, cfg=encoder_cfg, input=sequence["path"],
            width=sequence["width"], height=sequence["height"],
            fps=sequence.get("fps", 30), frames=sequence.get("frames", 100),
            qp=qp, bitstream=output_bitstream, recon=output_recon,
            bit_depth=bit_depth, chroma_format=chroma_format,
        )
        cmd = shlex.split(cmd_str)
    except (KeyError, ValueError) as e:
        return EncodingResult(
            sequence=seq_name, qp=qp, config_label=config_label,
            bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
            encode_time_s=0, status="failed",
            error=f"Command template error: {e}. Template: {cmd_template}",
        )

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
                sequence=seq_name, qp=qp, config_label=config_label,
                bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
                encode_time_s=elapsed, status="failed",
                error=f"Exit code {proc.returncode}: {proc.stderr[:500]}",
            )

        metrics = parse_encoder_output(proc.stdout, proc.stderr, parsing_config, chroma_format)

        # (3-1) Validate parsed metrics — zero values indicate parsing failure
        if metrics["bitrate_kbps"] <= 0 or metrics["psnr_y"] <= 0:
            return EncodingResult(
                sequence=seq_name, qp=qp, config_label=config_label,
                bitrate_kbps=metrics["bitrate_kbps"],
                psnr_y=metrics["psnr_y"], psnr_u=metrics["psnr_u"],
                psnr_v=metrics["psnr_v"], psnr_yuv=metrics["psnr_yuv"],
                encode_time_s=elapsed, status="failed",
                error=(
                    f"Metric parsing failed: bitrate={metrics['bitrate_kbps']}, "
                    f"psnr_y={metrics['psnr_y']}. "
                    "Check encoder output format or configure output_parsing patterns."
                ),
            )

        ssim_val = metrics.get("ssim")
        vmaf_val = None

        # SSIM: opt-in (from encoder output or ffmpeg fallback)
        if "ssim" in quality_metrics and ssim_val is None:
            ssim_val = _run_ffmpeg_ssim(
                sequence["path"], output_recon,
                sequence["width"], sequence["height"], bit_depth,
            )

        # VMAF: opt-in (always via ffmpeg)
        if "vmaf" in quality_metrics:
            vmaf_val = _run_ffmpeg_vmaf(
                sequence["path"], output_recon,
                sequence["width"], sequence["height"], bit_depth,
            )

        return EncodingResult(
            sequence=seq_name, qp=qp, config_label=config_label,
            bitrate_kbps=metrics["bitrate_kbps"],
            psnr_y=metrics["psnr_y"], psnr_u=metrics["psnr_u"],
            psnr_v=metrics["psnr_v"], psnr_yuv=metrics["psnr_yuv"],
            encode_time_s=elapsed, status="success",
            ssim=ssim_val, vmaf=vmaf_val,
        )

    except subprocess.TimeoutExpired:
        return EncodingResult(
            sequence=seq_name, qp=qp, config_label=config_label,
            bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
            encode_time_s=timeout, status="failed",
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return EncodingResult(
            sequence=seq_name, qp=qp, config_label=config_label,
            bitrate_kbps=0, psnr_y=0, psnr_u=0, psnr_v=0, psnr_yuv=0,
            encode_time_s=time.time() - start, status="failed",
            error=str(e),
        )


def _resolve_configs(config: dict) -> list:
    """Resolve anchor/test or candidates[] into a list of (cfg_dict, is_anchor) tuples.

    Returns:
        List of (config_entry_dict, is_anchor_bool) tuples.
        config_entry_dict has: encoder_binary, encoder_cfg, label, encoder_src (optional),
            encoder_cmd_template (optional).
    """
    # candidates[] takes priority over anchor/test
    candidates = config.get("candidates")
    if candidates and len(candidates) >= 2:
        resolved = []
        has_anchor = False
        for c in candidates:
            is_anchor = c.get("is_anchor", False)
            if is_anchor:
                has_anchor = True
            resolved.append((c, is_anchor))
        # If no explicit anchor, first entry is anchor
        if not has_anchor and resolved:
            resolved[0] = (resolved[0][0], True)
        return resolved

    # Fallback: anchor/test pair
    result = []
    if "anchor" in config:
        result.append((config["anchor"], True))
    if "test" in config:
        result.append((config["test"], False))
    return result


def run_local(config: dict, output_dir: str) -> list:
    """Run all encoding jobs locally in parallel."""
    max_parallel = config.get("execution", {}).get("max_parallel", os.cpu_count() or 4)
    timeout = config.get("execution", {}).get("timeout_per_job", 3600)
    sequences = config["sequences"]
    qp_points = config["qp_points"]
    global_cmd_template = config.get("encoder_cmd_template", DEFAULT_CMD_TEMPLATE)
    parsing_config = config.get("output_parsing")
    quality_metrics = config.get("quality_metrics", ["psnr"])

    configs = _resolve_configs(config)

    # Build job list for all configs
    jobs = []
    for cfg_entry, is_anchor in configs:
        encoder_binary = cfg_entry.get("encoder_binary", "")
        encoder_cfg = cfg_entry.get("encoder_cfg", "")
        label = cfg_entry.get("label", "unknown")
        cmd_template = cfg_entry.get("encoder_cmd_template", global_cmd_template)

        for seq in sequences:
            for qp in qp_points:
                jobs.append((
                    encoder_binary, encoder_cfg, seq, qp, label, output_dir, timeout,
                    cmd_template, parsing_config, quality_metrics, is_anchor,
                ))

    total = len(jobs)
    results = []
    completed = 0

    print(f"Running {total} encoding jobs (max {max_parallel} parallel)...")
    print(f"  Configs: {len(configs)}, Sequences: {len(sequences)}, QPs: {qp_points}")

    with ProcessPoolExecutor(max_workers=max_parallel) as executor:
        futures = {
            executor.submit(run_single_encode, *job[:-1]): job
            for job in jobs
        }

        for future in as_completed(futures):
            job = futures[future]
            is_anchor = job[-1]  # last element is is_anchor flag
            result = future.result()
            result.is_anchor = is_anchor
            results.append(result)
            completed += 1

            status_icon = "OK" if result.status == "success" else "FAIL"
            extra = ""
            if result.ssim is not None:
                extra += f" SSIM={result.ssim:.4f}"
            if result.vmaf is not None:
                extra += f" VMAF={result.vmaf:.1f}"
            print(f"  [{completed}/{total}] {status_icon} {result.config_label} / "
                  f"{result.sequence} / QP={result.qp} "
                  f"({result.encode_time_s:.1f}s){extra}")

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
