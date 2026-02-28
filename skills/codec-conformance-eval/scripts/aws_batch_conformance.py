#!/usr/bin/env python3
"""aws_batch_conformance.py — AWS Batch submission for conformance decoding jobs.

Submits decoder conformance jobs to AWS Batch for cost-efficient large-scale evaluation
using spot instances. Follows the same pattern as codec-rd-eval/aws_batch_submit.py.

Requires:
  - AWS credentials (aws configure or IAM role)
  - boto3: pip install boto3
  - AWS Batch infrastructure (job queue, job definition, compute environment)
  - Conformance bitstreams and decoder on S3

Usage:
    python3 aws_batch_conformance.py <config.json> --output-dir <dir>
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Optional


def submit_jobs(config: dict, output_dir: str, batch_client=None) -> list:
    """Submit conformance decoding jobs to AWS Batch.

    Args:
        config: Conformance configuration dict (JSON, not HJSON)
        output_dir: Local directory for results
        batch_client: Optional pre-created boto3 Batch client

    Returns:
        List of submitted job info dicts.
    """
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3", file=sys.stderr)
        sys.exit(1)

    aws_cfg = config.get("execution", {}).get("aws_batch", {})
    region = aws_cfg.get("region", "ap-northeast-2")
    job_queue = aws_cfg.get("job_queue", "codec-conformance-spot-queue")
    job_definition = aws_cfg.get("job_definition", "codec-conformance-job")
    timeout = config.get("execution", {}).get("timeout_per_job", 300)

    if batch_client is None:
        batch_client = boto3.client("batch", region_name=region)

    s3_bucket = aws_cfg.get("s3_bucket", "codec-eval-results")

    decoder_cfg = config.get("decoder", {})
    eval_name = config.get("eval_name", "conformance-eval")

    # Discover streams (simplified — expects pre-resolved stream list)
    streams = config.get("_resolved_streams", [])
    if not streams:
        print("WARNING: No resolved streams in config. "
              "Ensure run_conformance.py pre-resolves streams before AWS submission.",
              file=sys.stderr)
        return []

    submitted_jobs = []

    for stream in streams:
        stream_name = stream["name"]
        source_id = stream["source_id"]
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', stream_name)[:64]
        job_name = f"conf-{safe_name}"

        try:
            response = batch_client.submit_job(
                jobName=job_name,
                jobQueue=job_queue,
                jobDefinition=job_definition,
                containerOverrides={
                    "command": [
                        "/app/decode.sh",
                        "--bitstream", stream["s3_path"],
                        "--output-s3", f"s3://{s3_bucket}/{eval_name}/{safe_name}_decoded.yuv",
                    ],
                    "environment": [
                        {"name": "EVAL_NAME", "value": eval_name},
                        {"name": "STREAM_NAME", "value": stream_name},
                        {"name": "SOURCE_ID", "value": source_id},
                    ],
                },
                retryStrategy={"attempts": 2},
                timeout={"attemptDurationSeconds": timeout},
            )

            submitted_jobs.append({
                "job_id": response["jobId"],
                "job_name": job_name,
                "stream_name": stream_name,
                "source_id": source_id,
                "priority": stream.get("priority", "optional"),
            })

        except Exception as e:
            print(f"  ERROR submitting {stream_name}: {e}", file=sys.stderr)
            submitted_jobs.append({
                "job_id": None,
                "stream_name": stream_name,
                "source_id": source_id,
                "priority": stream.get("priority", "optional"),
                "error": str(e),
            })

    print(f"Submitted {len(submitted_jobs)} conformance jobs to AWS Batch")
    return submitted_jobs


def wait_for_jobs(batch_client, jobs: list, poll_interval: int = 30,
                  max_wait: int = 14400) -> list:
    """Wait for all AWS Batch jobs to complete.

    Args:
        batch_client: boto3 Batch client
        jobs: List of submitted job dicts with 'job_id'
        poll_interval: Seconds between status checks
        max_wait: Maximum total wait time in seconds (default: 4 hours)

    Returns:
        List of completed job info dicts.
    """
    pending_jobs = {j["job_id"]: j for j in jobs if j.get("job_id")}
    completed = []
    start_time = time.time()

    while pending_jobs:
        if time.time() - start_time > max_wait:
            print(f"  WARNING: Polling timeout after {max_wait}s. "
                  f"{len(pending_jobs)} jobs still pending.", file=sys.stderr)
            for jid, info in pending_jobs.items():
                info["status"] = "failed"
                info["error"] = f"Polling timeout after {max_wait}s"
                completed.append(info)
            pending_jobs.clear()
            break
        job_ids = list(pending_jobs.keys())

        # AWS Batch allows max 100 IDs per describe call
        for i in range(0, len(job_ids), 100):
            batch_ids = job_ids[i:i + 100]
            response = batch_client.describe_jobs(jobs=batch_ids)

            for job in response["jobs"]:
                jid = job["jobId"]
                status = job["status"]

                if status == "SUCCEEDED":
                    info = pending_jobs.pop(jid)
                    info["status"] = "success"
                    completed.append(info)
                elif status == "FAILED":
                    info = pending_jobs.pop(jid)
                    info["status"] = "failed"
                    reason = job.get("statusReason", "Unknown")
                    info["error"] = reason
                    completed.append(info)
                # else: SUBMITTED, PENDING, RUNNABLE, STARTING, RUNNING — keep waiting

        if pending_jobs:
            remaining = len(pending_jobs)
            print(f"  Waiting... {remaining} jobs remaining ({len(completed)} completed)")
            time.sleep(poll_interval)

    return completed


def fetch_job_result(s3_client, eval_name: str, stream_name: str,
                     s3_bucket: str = "codec-eval-results") -> Optional[dict]:
    """Fetch decoding result from S3.

    Args:
        s3_client: boto3 S3 client
        eval_name: Evaluation name (S3 prefix)
        stream_name: Stream name
        s3_bucket: S3 bucket name (from execution.aws_batch.s3_bucket config)

    Returns:
        Result dict with md5_decoded, decode_time_s, or None if not found.
    """
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', stream_name)[:64]
    s3_key = f"{eval_name}/{safe_name}_result.json"
    bucket = s3_bucket

    try:
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="AWS Batch conformance job submission")
    parser.add_argument("config", help="JSON configuration file")
    parser.add_argument("--output-dir", required=True, help="Output directory for results")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3", file=sys.stderr)
        sys.exit(1)

    aws_cfg = config.get("execution", {}).get("aws_batch", {})
    region = aws_cfg.get("region", "ap-northeast-2")
    batch_client = boto3.client("batch", region_name=region)
    s3_client = boto3.client("s3", region_name=region)

    # Submit jobs (reuse batch_client created above)
    submitted = submit_jobs(config, args.output_dir, batch_client=batch_client)

    if not submitted:
        print("ERROR: No jobs were submitted. Check _resolved_streams in config.",
              file=sys.stderr)
        sys.exit(1)

    # Wait for completion
    completed = wait_for_jobs(batch_client, submitted)

    # Fetch results
    eval_name = config.get("eval_name", "conformance-eval")
    s3_bucket = aws_cfg.get("s3_bucket", "codec-eval-results")
    results = []

    # Include submit-failed jobs (job_id=None) that wait_for_jobs skips
    for job in submitted:
        if job.get("job_id") is None and job.get("error"):
            results.append({
                "stream_name": job["stream_name"],
                "source_id": job.get("source_id", ""),
                "source_priority": job.get("priority", "optional"),
                "status": "failed",
                "md5_decoded": None,
                "decode_time_s": 0,
                "error": f"Submit failed: {job['error']}",
            })

    for job in completed:
        stream_name = job["stream_name"]

        if job.get("status") == "success":
            s3_result = fetch_job_result(s3_client, eval_name, stream_name, s3_bucket)
            if s3_result:
                results.append({
                    "stream_name": stream_name,
                    "source_id": job["source_id"],
                    "source_priority": job.get("priority", "optional"),
                    "status": "success",
                    "md5_decoded": s3_result.get("md5_decoded"),
                    "decode_time_s": s3_result.get("decode_time_s", 0),
                    "output_path": s3_result.get("output_path"),
                })
            else:
                results.append({
                    "stream_name": stream_name,
                    "source_id": job["source_id"],
                    "source_priority": job.get("priority", "optional"),
                    "status": "failed",
                    "md5_decoded": None,
                    "decode_time_s": 0,
                    "error": "S3 result not found",
                })
        else:
            results.append({
                "stream_name": stream_name,
                "source_id": job["source_id"],
                "source_priority": job.get("priority", "optional"),
                "status": "failed",
                "md5_decoded": None,
                "decode_time_s": 0,
                "error": job.get("error", "Job failed"),
            })

    # Save results
    results_path = os.path.join(args.output_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n=== AWS Batch conformance: {success} succeeded, {failed} failed ===")
    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
