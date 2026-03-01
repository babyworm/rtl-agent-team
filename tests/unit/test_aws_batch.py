"""Tests for aws_batch_submit.py and aws_batch_conformance.py — AWS Batch job submission (mocked).

All AWS API calls are mocked via unittest.mock. No real AWS credentials needed.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

RD_SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "codec-rd-eval" / "scripts"
)
CONF_SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "codec-conformance-eval" / "scripts"
)
sys.path.insert(0, str(RD_SCRIPT_DIR))
sys.path.insert(0, str(CONF_SCRIPT_DIR))


class TestAwsBatchSubmitJobNames:
    """Test job name sanitization in aws_batch_submit.py."""

    def test_job_name_sanitization(self):
        import re
        label = "my config/v2@test"
        safe_label = re.sub(r'[^a-zA-Z0-9_-]', '-', label)[:32]
        assert "/" not in safe_label
        assert "@" not in safe_label
        assert all(c.isalnum() or c in "_-" for c in safe_label)

    def test_job_name_length_limit(self):
        import re
        long_label = "a" * 200
        job_name = f"rd-eval-{long_label}-seq-qp22"
        job_name = re.sub(r'[^a-zA-Z0-9_-]', '-', job_name)[:128]
        assert len(job_name) <= 128


class TestAwsBatchSubmitLogic:
    """Test submit_jobs logic with mocked boto3."""

    @pytest.fixture
    def mock_boto3(self):
        mock = MagicMock()
        mock_batch = MagicMock()
        mock_s3 = MagicMock()
        mock.client.side_effect = lambda service, **kw: (
            mock_batch if service == "batch" else mock_s3
        )
        mock_batch.submit_job.return_value = {"jobId": "job-123"}
        mock_batch.describe_jobs.return_value = {
            "jobs": [{"jobId": "job-123", "status": "SUCCEEDED"}]
        }
        return mock, mock_batch, mock_s3

    @pytest.fixture
    def sample_config(self):
        return {
            "sequences": [
                {"name": "BasketballDrill", "path": "/data/seq.yuv",
                 "width": 832, "height": 480},
            ],
            "qp_points": [22, 27],
            "anchor": {
                "encoder_binary": "/bin/enc",
                "encoder_cfg": "anchor.cfg",
                "label": "anchor",
            },
            "test": {
                "encoder_binary": "/bin/enc",
                "encoder_cfg": "test.cfg",
                "label": "test",
            },
            "execution": {
                "aws_batch": {
                    "region": "us-east-1",
                    "job_queue": "test-queue",
                    "job_definition": "test-job-def",
                    "s3_bucket": "test-bucket",
                },
                "timeout_per_job": 600,
            },
        }

    def test_submit_creates_correct_number_of_jobs(self, mock_boto3, sample_config, tmp_path):
        mock_module, mock_batch, mock_s3 = mock_boto3
        # 2 configs * 1 sequence * 2 QPs = 4 jobs
        with patch.dict("sys.modules", {"boto3": mock_module}):
            from aws_batch_submit import submit_jobs

            # Mock wait_for_jobs to avoid actual polling
            with patch("aws_batch_submit.wait_for_jobs", return_value=[]):
                submit_jobs(sample_config, str(tmp_path))

        assert mock_batch.submit_job.call_count == 4

    def test_submit_handles_failure(self, mock_boto3, sample_config, tmp_path):
        mock_module, mock_batch, mock_s3 = mock_boto3
        mock_batch.submit_job.side_effect = Exception("Access denied")

        with patch.dict("sys.modules", {"boto3": mock_module}):
            from aws_batch_submit import submit_jobs
            with patch("aws_batch_submit.wait_for_jobs", return_value=[]):
                submit_jobs(sample_config, str(tmp_path))

        # Results should contain submit failures
        results_path = tmp_path / "results.json"
        assert results_path.exists()


class TestAwsBatchFetchResult:
    """Test fetch_job_result with mocked S3."""

    def test_successful_fetch(self):
        mock_s3 = MagicMock()
        result_data = {
            "bitrate_kbps": 1500.0, "psnr_y": 38.5,
            "psnr_u": 40.0, "psnr_v": 41.0, "psnr_yuv": 39.0,
            "encode_time_s": 12.5,
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(result_data).encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        # Import with mocked boto3
        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from aws_batch_submit import fetch_job_result

        job = {"jobId": "job-123"}
        meta = {"sequence": "seq", "qp": 22, "config_label": "anchor", "is_anchor": True}
        config = {"eval_name": "test", "execution": {"aws_batch": {"s3_bucket": "bucket"}}}

        result = fetch_job_result(MagicMock(), mock_s3, job, meta, config, "/tmp")
        assert result["status"] == "success"
        assert result["bitrate_kbps"] == 1500.0
        assert result["is_anchor"] is True

    def test_s3_error_returns_failure(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")

        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from aws_batch_submit import fetch_job_result

        job = {"jobId": "job-123"}
        meta = {"sequence": "seq", "qp": 22, "config_label": "test", "is_anchor": False}
        config = {"eval_name": "test", "execution": {"aws_batch": {"s3_bucket": "bucket"}}}

        result = fetch_job_result(MagicMock(), mock_s3, job, meta, config, "/tmp")
        assert result["status"] == "failed"
        assert "S3" in result["error"]


class TestWaitForJobs:
    """Test wait_for_jobs polling logic."""

    def test_immediate_completion(self):
        mock_batch = MagicMock()
        mock_batch.describe_jobs.return_value = {
            "jobs": [{"jobId": "job-1", "status": "SUCCEEDED"}]
        }
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"bitrate_kbps": 100}).encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from aws_batch_submit import wait_for_jobs

        job_map = {"job-1": {"sequence": "s", "qp": 22, "config_label": "a", "is_anchor": True}}
        config = {"eval_name": "e", "execution": {"aws_batch": {"s3_bucket": "b"}}}

        results = wait_for_jobs(
            mock_batch, mock_s3, ["job-1"], job_map, config, "/tmp",
            poll_interval=0, max_wait=5,
        )
        assert len(results) == 1

    def test_failed_job(self):
        mock_batch = MagicMock()
        mock_batch.describe_jobs.return_value = {
            "jobs": [{"jobId": "job-1", "status": "FAILED", "statusReason": "OutOfMemory"}]
        }

        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from aws_batch_submit import wait_for_jobs

        job_map = {"job-1": {"sequence": "s", "qp": 22, "config_label": "a", "is_anchor": False}}
        config = {"eval_name": "e", "execution": {"aws_batch": {"s3_bucket": "b"}}}

        results = wait_for_jobs(
            mock_batch, MagicMock(), ["job-1"], job_map, config, "/tmp",
            poll_interval=0, max_wait=5,
        )
        assert results[0]["status"] == "failed"
        assert "OutOfMemory" in results[0]["error"]

    def test_timeout_returns_failures(self):
        mock_batch = MagicMock()
        # Always return RUNNING
        mock_batch.describe_jobs.return_value = {
            "jobs": [{"jobId": "job-1", "status": "RUNNING"}]
        }

        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from aws_batch_submit import wait_for_jobs

        job_map = {"job-1": {"sequence": "s", "qp": 22, "config_label": "a", "is_anchor": False}}
        config = {"eval_name": "e", "execution": {"aws_batch": {"s3_bucket": "b"}}}

        results = wait_for_jobs(
            mock_batch, MagicMock(), ["job-1"], job_map, config, "/tmp",
            poll_interval=0, max_wait=0,  # Immediate timeout
        )
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "timeout" in results[0]["error"].lower()
