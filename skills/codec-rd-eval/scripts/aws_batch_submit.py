#!/usr/bin/env python3
"""aws_batch_submit.py — AWS Batch spot instance job submission for codec RD evaluation.

Submits encoding jobs to AWS Batch using spot instances for cost-efficient large-scale
evaluation. This is an opt-in mode activated via execution.mode="aws-batch" in the
HJSON test configuration.

Prerequisites:
    - AWS credentials configured (aws configure or IAM role)
    - boto3 installed (pip install boto3)
    - AWS Batch infrastructure set up (job queue, job definition, compute environment)
    - Test sequences uploaded to S3

Usage:
    python3 aws_batch_submit.py <config.json> --output-dir <dir>

The config.json should be the full eval configuration (JSON format, converted from HJSON
by run_eval.py).
"""

import argparse
import json
import os
import sys
import time


def check_boto3():
    """Check if boto3 is available."""
    try:
        import boto3
        return boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3", file=sys.stderr)
        print("AWS Batch mode requires: pip install boto3", file=sys.stderr)
        sys.exit(1)


def submit_jobs(config: dict, output_dir: str):
    """Submit encoding jobs to AWS Batch.

    Args:
        config: Full evaluation configuration
        output_dir: Local directory for results
    """
    boto3 = check_boto3()

    aws_cfg = config.get("execution", {}).get("aws_batch", {})
    region = aws_cfg.get("region", "ap-northeast-2")
    job_queue = aws_cfg.get("job_queue", "codec-eval-spot-queue")
    job_definition = aws_cfg.get("job_definition", "codec-eval-job")

    s3_bucket = aws_cfg.get("s3_bucket", "codec-eval-results")

    batch_client = boto3.client("batch", region_name=region)
    s3_client = boto3.client("s3", region_name=region)

    sequences = config.get("sequences", [])
    qp_points = config.get("qp_points", [])
    if not sequences or not qp_points:
        print("ERROR: sequences and qp_points are required in config.", file=sys.stderr)
        return
    timeout = config.get("execution", {}).get("timeout_per_job", 3600)

    # Resolve configs: support both candidates[] and anchor/test modes
    resolved_configs = []
    candidates = config.get("candidates")
    if candidates and len(candidates) >= 2:
        has_anchor = any(c.get("is_anchor") for c in candidates)
        for i, c in enumerate(candidates):
            is_anchor = c.get("is_anchor", False) or (i == 0 and not has_anchor)
            resolved_configs.append((c, is_anchor))
    else:
        if "anchor" in config:
            resolved_configs.append((config["anchor"], True))
        if "test" in config:
            resolved_configs.append((config["test"], False))

    job_ids = []
    job_map = {}  # job_id → metadata

    for cfg, is_anchor in resolved_configs:
        label = cfg.get("label", "anchor" if is_anchor else "test")
        encoder_cfg = cfg.get("encoder_cfg", "")

        for seq in sequences:
            for qp in qp_points:
                safe_label = "".join(c if c.isalnum() or c == "-" else "-" for c in label)[:32]
                job_name = f"rd-eval-{safe_label}-{seq['name']}-qp{qp}"
                # Sanitize job name (AWS Batch: alphanumeric + hyphens, max 128 chars)
                job_name = "".join(c if c.isalnum() or c == "-" else "-" for c in job_name)[:128]

                try:
                    response = batch_client.submit_job(
                        jobName=job_name,
                        jobQueue=job_queue,
                        jobDefinition=job_definition,
                        containerOverrides={
                            "command": [
                                "/app/encode.sh",
                                "--config", encoder_cfg,
                                "--input", seq["path"],
                                "--width", str(seq["width"]),
                                "--height", str(seq["height"]),
                                "--fps", str(seq.get("fps", 30)),
                                "--frames", str(seq.get("frames", 100)),
                                "--qp", str(qp),
                                "--output-s3", f"s3://{s3_bucket}/{config.get('eval_name', 'eval')}/",
                            ],
                            "environment": [
                                {"name": "EVAL_NAME", "value": config.get("eval_name", "eval")},
                                {"name": "CONFIG_LABEL", "value": label},
                                {"name": "SEQUENCE_NAME", "value": seq["name"]},
                                {"name": "QP", "value": str(qp)},
                            ],
                        },
                        timeout={"attemptDurationSeconds": timeout},
                        retryStrategy={"attempts": 2},  # Retry once for spot interruptions
                    )

                    job_id = response["jobId"]
                    job_ids.append(job_id)
                    job_map[job_id] = {
                        "sequence": seq["name"],
                        "qp": qp,
                        "config_label": label,
                        "is_anchor": is_anchor,
                    }
                    print(f"  Submitted: {job_name} → {job_id}")

                except Exception as e:
                    print(f"  FAILED to submit {job_name}: {e}", file=sys.stderr)
                    # Track failed submissions in results
                    job_map[f"submit-fail-{len(job_map)}"] = {
                        "sequence": seq["name"],
                        "qp": qp,
                        "config_label": label,
                        "is_anchor": is_anchor,
                        "submit_error": str(e),
                    }

    # Include submission failures in results immediately
    submit_failures = []
    for key, meta in job_map.items():
        if "submit_error" in meta:
            submit_failures.append({
                "sequence": meta["sequence"],
                "qp": meta["qp"],
                "config_label": meta["config_label"],
                "bitrate_kbps": 0, "psnr_y": 0, "psnr_u": 0,
                "psnr_v": 0, "psnr_yuv": 0, "encode_time_s": 0,
                "status": "failed",
                "error": f"Submit failed: {meta['submit_error']}",
                "is_anchor": meta.get("is_anchor", False),
            })

    print(f"\nSubmitted {len(job_ids)} jobs to AWS Batch ({region})")
    if submit_failures:
        print(f"  ({len(submit_failures)} jobs failed to submit)")
    print(f"Job queue: {job_queue}")

    # Poll for completion
    print("\nWaiting for jobs to complete...")
    results = wait_for_jobs(batch_client, s3_client, job_ids, job_map, config, output_dir)
    results.extend(submit_failures)

    # Save results
    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_path}")


def wait_for_jobs(batch_client, s3_client, job_ids: list, job_map: dict,
                  config: dict, output_dir: str, poll_interval: int = 30,
                  max_wait: int = 14400) -> list:
    """Poll AWS Batch jobs until all complete or fail.

    Args:
        batch_client: boto3 Batch client
        s3_client: boto3 S3 client
        job_ids: List of submitted job IDs
        job_map: Job ID → metadata mapping
        config: Evaluation configuration
        output_dir: Local output directory
        poll_interval: Seconds between status checks
        max_wait: Maximum total wait time in seconds (default: 4 hours)

    Returns:
        List of result dictionaries
    """
    pending = set(job_ids)
    results = []
    start_time = time.time()

    while pending:
        if time.time() - start_time > max_wait:
            print(f"  WARNING: Polling timeout after {max_wait}s. "
                  f"{len(pending)} jobs still pending.", file=sys.stderr)
            for job_id in list(pending):
                meta = job_map[job_id]
                results.append({
                    "sequence": meta["sequence"],
                    "qp": meta["qp"],
                    "config_label": meta["config_label"],
                    "bitrate_kbps": 0, "psnr_y": 0, "psnr_u": 0,
                    "psnr_v": 0, "psnr_yuv": 0, "encode_time_s": 0,
                    "status": "failed",
                    "error": f"Polling timeout after {max_wait}s",
                    "is_anchor": meta.get("is_anchor", False),
                })
                pending.discard(job_id)
            break
        # AWS Batch describe_jobs supports up to 100 IDs per call
        pending_list = list(pending)
        for i in range(0, len(pending_list), 100):
            batch = pending_list[i:i+100]
            response = batch_client.describe_jobs(jobs=batch)

            for job in response.get("jobs", []):
                job_id = job["jobId"]
                status = job["status"]

                if status in ("SUCCEEDED", "FAILED"):
                    meta = job_map[job_id]
                    if status == "SUCCEEDED":
                        # Fetch results from CloudWatch Logs or S3
                        result = fetch_job_result(
                            batch_client, s3_client, job, meta, config, output_dir
                        )
                        results.append(result)
                    else:
                        reason = job.get("statusReason", "Unknown")
                        results.append({
                            "sequence": meta["sequence"],
                            "qp": meta["qp"],
                            "config_label": meta["config_label"],
                            "bitrate_kbps": 0, "psnr_y": 0, "psnr_u": 0,
                            "psnr_v": 0, "psnr_yuv": 0, "encode_time_s": 0,
                            "status": "failed",
                            "error": f"AWS Batch FAILED: {reason}",
                            "is_anchor": meta.get("is_anchor", False),
                        })
                    pending.discard(job_id)

        if pending:
            completed = len(job_ids) - len(pending)
            print(f"  Progress: {completed}/{len(job_ids)} complete, "
                  f"{len(pending)} pending...")
            time.sleep(poll_interval)

    return results


def fetch_job_result(batch_client, s3_client, job: dict, meta: dict,
                     config: dict, output_dir: str) -> dict:
    """Fetch encoding results from a completed AWS Batch job.

    Results are expected in S3 at the configured output path,
    or parsed from CloudWatch Logs.
    """
    eval_name = config.get("eval_name", "eval")
    seq = meta["sequence"]
    qp = meta["qp"]
    label = meta["config_label"]

    result_key = f"{eval_name}/{label}_{seq}_qp{qp}_result.json"
    bucket = config.get("execution", {}).get("aws_batch", {}).get(
        "s3_bucket", "codec-eval-results")

    try:
        obj = s3_client.get_object(Bucket=bucket, Key=result_key)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        return {
            "sequence": seq,
            "qp": qp,
            "config_label": label,
            "bitrate_kbps": data.get("bitrate_kbps", 0),
            "psnr_y": data.get("psnr_y", 0),
            "psnr_u": data.get("psnr_u", 0),
            "psnr_v": data.get("psnr_v", 0),
            "psnr_yuv": data.get("psnr_yuv", 0),
            "encode_time_s": data.get("encode_time_s", 0),
            "status": "success",
            "ssim": data.get("ssim"),
            "vmaf": data.get("vmaf"),
            "is_anchor": meta.get("is_anchor", False),
        }
    except Exception as e:
        return {
            "sequence": seq,
            "qp": qp,
            "config_label": label,
            "bitrate_kbps": 0, "psnr_y": 0, "psnr_u": 0,
            "psnr_v": 0, "psnr_yuv": 0, "encode_time_s": 0,
            "status": "failed",
            "error": f"Failed to fetch result from S3: {e}",
            "is_anchor": meta.get("is_anchor", False),
        }


def main():
    parser = argparse.ArgumentParser(description="AWS Batch submission for codec RD eval")
    parser.add_argument("config", help="Evaluation configuration (JSON)")
    parser.add_argument("--output-dir", required=True, help="Output directory for results")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)
    submit_jobs(config, args.output_dir)


if __name__ == "__main__":
    main()
