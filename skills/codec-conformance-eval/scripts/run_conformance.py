#!/usr/bin/env python3
"""run_conformance.py — Parallel conformance test orchestrator for decoder evaluation.

Parses HJSON conformance configuration, runs decoder across all conformance bitstreams
in parallel, and collects decoding results (status, MD5, decode time).

Usage:
    python3 run_conformance.py <config.hjson> --mode local [--max-parallel N]
    python3 run_conformance.py <config.hjson> --mode aws-batch

Dependencies: hjson
"""

import argparse
import glob
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Optional


# Default decoder CLI template
DEFAULT_DECODER_CMD_TEMPLATE = "{decoder} -b {bitstream} -o {output} {extra_args}"

# Conformance bitstream file extensions by standard
# Note: *.bin is excluded from auto-discovery to avoid false matches.
# If conformance streams use .bin extension, list them explicitly in config streams[].
STREAM_EXTENSIONS = {
    "h264": ["*.264", "*.h264", "*.avc"],
    "h265": ["*.265", "*.h265", "*.hevc"],
}


@dataclass
class DecodingResult:
    """Result of a single conformance decoding run."""
    stream_name: str
    source_id: str
    source_priority: str  # "mandatory" | "optional"
    status: str  # "success" | "failed"
    md5_decoded: Optional[str] = None
    decode_time_s: float = 0.0
    output_path: Optional[str] = None
    error: Optional[str] = None


def load_config(config_path: str) -> dict:
    """Load HJSON conformance configuration."""
    try:
        import hjson
    except ImportError:
        print("ERROR: hjson package not installed. Run: pip install hjson", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        return hjson.load(f)


def discover_streams(source: dict, standard: str) -> list:
    """Auto-discover conformance bitstreams from a source directory.

    Args:
        source: Conformance source config dict with 'path' and optional 'streams'.
        standard: Target standard ("h264" or "h265").

    Returns:
        List of dicts: {name, path, source_id, priority}
    """
    explicit_streams = source.get("streams", [])
    if explicit_streams:
        return [
            {
                "name": s.get("name", Path(s["path"]).stem),
                "path": s["path"],
                "source_id": source["id"],
                "priority": source.get("priority", "optional"),
            }
            for s in explicit_streams
        ]

    # Auto-discover from directory
    base_path = source.get("path", "")
    if not os.path.isdir(base_path):
        print(f"  WARNING: Conformance source path not found: {base_path}", file=sys.stderr)
        return []

    extensions = STREAM_EXTENSIONS.get(standard, ["*.bin"])
    found = []
    for ext in extensions:
        for filepath in sorted(glob.glob(os.path.join(base_path, "**", ext), recursive=True)):
            name = Path(filepath).stem
            # Avoid duplicates (same stem from different extensions, e.g. foo.264 vs foo.bin)
            # Keeps whichever extension is discovered first
            if not any(f["name"] == name for f in found):
                found.append({
                    "name": name,
                    "path": filepath,
                    "source_id": source["id"],
                    "priority": source.get("priority", "optional"),
                })

    return found


def compute_md5(filepath: str) -> Optional[str]:
    """Compute MD5 checksum of a file."""
    if not os.path.isfile(filepath):
        return None
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_single_decode(
    decoder_binary: str,
    stream: dict,
    output_dir: str,
    timeout: int,
    cmd_template: str = DEFAULT_DECODER_CMD_TEMPLATE,
    extra_args: str = "",
) -> DecodingResult:
    """Run a single conformance decoding job."""
    stream_name = stream["name"]
    source_id = stream["source_id"]
    priority = stream["priority"]

    safe_name = re.sub(r'[^\w\-.]', '_', stream_name)
    if len(safe_name) > 64:
        h = hashlib.md5(stream_name.encode()).hexdigest()[:6]
        safe_name = f"{safe_name[:57]}_{h}"
    output_yuv = os.path.join(output_dir, f"{safe_name}_decoded.yuv")

    try:
        cmd_str = cmd_template.format(
            decoder=shlex.quote(decoder_binary),
            bitstream=shlex.quote(stream["path"]),
            output=shlex.quote(output_yuv),
            extra_args=extra_args,
        )
        cmd = shlex.split(cmd_str)
    except (KeyError, ValueError) as e:
        return DecodingResult(
            stream_name=stream_name, source_id=source_id,
            source_priority=priority, status="failed",
            error=f"Command template error: {e}",
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
            return DecodingResult(
                stream_name=stream_name, source_id=source_id,
                source_priority=priority, status="failed",
                decode_time_s=elapsed,
                error=f"Exit code {proc.returncode}: {proc.stderr[:500]}",
            )

        # Compute MD5 of decoded output
        md5 = compute_md5(output_yuv)

        return DecodingResult(
            stream_name=stream_name, source_id=source_id,
            source_priority=priority, status="success",
            md5_decoded=md5, decode_time_s=elapsed,
            output_path=output_yuv,
        )

    except subprocess.TimeoutExpired:
        return DecodingResult(
            stream_name=stream_name, source_id=source_id,
            source_priority=priority, status="failed",
            decode_time_s=timeout,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return DecodingResult(
            stream_name=stream_name, source_id=source_id,
            source_priority=priority, status="failed",
            decode_time_s=time.time() - start,
            error=str(e),
        )


def run_local(config: dict, output_dir: str) -> list:
    """Run all conformance decoding jobs locally in parallel."""
    execution = config.get("execution", {})
    max_parallel = execution.get("max_parallel", os.cpu_count() or 4)
    timeout = execution.get("timeout_per_job", 300)

    decoder_cfg = config.get("decoder", {})
    decoder_binary = decoder_cfg.get("decoder_binary", "")
    cmd_template = decoder_cfg.get("decoder_cmd_template", DEFAULT_DECODER_CMD_TEMPLATE)
    extra_args = decoder_cfg.get("extra_args", "")

    target = config.get("target", {})
    standard = target.get("standard", "h264")

    # Profile/level filtering (optional)
    target_profile = target.get("profile", "").lower()
    target_level = target.get("level", "")

    # Discover all conformance streams
    all_streams = []
    for source in config.get("conformance_sources", []):
        streams = discover_streams(source, standard)
        # Filter by profile/level if specified (filename convention based)
        # Uses word-boundary regex to avoid false matches (e.g., "main" in "domain")
        if target_profile:
            before = len(streams)
            profile_re = re.compile(r'(?:^|[\W_])' + re.escape(target_profile) + r'(?:[\W_]|$)', re.I)
            streams = [s for s in streams if profile_re.search(s["name"])]
            if len(streams) < before:
                print(f"  Profile filter '{target_profile}': {before} → {len(streams)} streams")
        all_streams.extend(streams)
        print(f"  Source '{source['id']}' ({source.get('priority', 'optional')}): "
              f"{len(streams)} streams found")

    if not all_streams:
        print("ERROR: No conformance bitstreams found.", file=sys.stderr)
        return []

    total = len(all_streams)
    results = []
    completed = 0

    print(f"\nRunning {total} conformance decoding jobs (max {max_parallel} parallel)...")

    with ProcessPoolExecutor(max_workers=max_parallel) as executor:
        futures = {
            executor.submit(
                run_single_decode,
                decoder_binary, stream, output_dir, timeout, cmd_template, extra_args,
            ): stream
            for stream in all_streams
        }

        for future in as_completed(futures):
            stream = futures[future]
            try:
                result = future.result()
            except Exception as e:
                # BrokenProcessPool or other executor-level failure
                result = DecodingResult(
                    stream_name=stream["name"], source_id=stream["source_id"],
                    source_priority=stream.get("priority", "optional"),
                    status="failed",
                    error=f"Executor error: {e}",
                )
            results.append(result)
            completed += 1

            status_icon = "OK" if result.status == "success" else "FAIL"
            print(f"  [{completed}/{total}] {status_icon} [{result.source_id}] "
                  f"{result.stream_name} ({result.decode_time_s:.1f}s)")

    return results


def run_aws_batch(config: dict, output_dir: str) -> list:
    """Submit conformance decoding jobs to AWS Batch."""
    print("AWS Batch mode: delegating to aws_batch_conformance.py...")
    aws_script = os.path.join(os.path.dirname(__file__), "aws_batch_conformance.py")

    # Pre-resolve streams so aws_batch_conformance.py can find them
    target = config.get("target", {})
    standard = target.get("standard", "h264")
    target_profile = target.get("profile", "").lower()
    s3_bucket = config.get("execution", {}).get("aws_batch", {}).get(
        "s3_bucket", "codec-eval-results")

    all_streams = []
    for source in config.get("conformance_sources", []):
        streams = discover_streams(source, standard)
        # Use word-boundary regex (consistent with run_local filter)
        if target_profile:
            profile_re = re.compile(
                r'(?:^|[\W_])' + re.escape(target_profile) + r'(?:[\W_]|$)', re.I)
            streams = [s for s in streams if profile_re.search(s["name"])]
        for s in streams:
            # Add s3_path: use explicit s3_path if present, else derive from local path
            if "s3_path" not in s:
                s["s3_path"] = f"s3://{s3_bucket}/conformance/{s['path'].lstrip('/')}"
        all_streams.extend(streams)

    if not all_streams:
        print("ERROR: No conformance bitstreams found for AWS Batch.", file=sys.stderr)
        return []

    config["_resolved_streams"] = all_streams
    print(f"  Resolved {len(all_streams)} streams for AWS Batch submission")

    config_path = os.path.join(output_dir, "conformance_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    try:
        proc = subprocess.run(
            [sys.executable, aws_script, config_path, "--output-dir", output_dir],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min for submission + polling
        )
    except subprocess.TimeoutExpired:
        print("ERROR: AWS Batch script timed out after 600s", file=sys.stderr)
        sys.exit(1)

    if proc.returncode != 0:
        print(f"ERROR: AWS Batch submission failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "r") as f:
        raw = json.load(f)
    known = {f.name for f in fields(DecodingResult)}
    return [DecodingResult(**{k: v for k, v in r.items() if k in known}) for r in raw]


def main():
    parser = argparse.ArgumentParser(description="Decoder conformance test orchestrator")
    parser.add_argument("config", help="HJSON conformance configuration file")
    parser.add_argument("--mode", choices=["local", "aws-batch"], default="local",
                        help="Execution mode (default: local)")
    parser.add_argument("--max-parallel", type=int, default=None,
                        help="Override max parallel jobs (local mode)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for results")
    args = parser.parse_args()

    config = load_config(args.config)

    output_dir = args.output_dir or config.get("output", {}).get(
        "raw_data_path", ".rtl-agent-team/scratch/conformance-eval"
    )
    os.makedirs(output_dir, exist_ok=True)

    if args.max_parallel:
        config.setdefault("execution", {})["max_parallel"] = args.max_parallel

    # Run decoding
    if args.mode == "local":
        results = run_local(config, output_dir)
    else:
        results = run_aws_batch(config, output_dir)

    # Summary
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    mandatory_fail = sum(1 for r in results
                         if r.status == "failed" and r.source_priority == "mandatory")

    print(f"\n=== Conformance complete: {success} succeeded, {failed} failed ===")
    if mandatory_fail > 0:
        print(f"  WARNING: {mandatory_fail} MANDATORY stream(s) FAILED!")

    if failed > 0:
        print("\nFailed streams:")
        for r in results:
            if r.status == "failed":
                tag = " [MANDATORY]" if r.source_priority == "mandatory" else ""
                print(f"  [{r.source_id}] {r.stream_name}{tag}: {r.error}")

    # Save results
    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
