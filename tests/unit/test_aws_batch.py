"""Tests for aws_batch_conformance.py — AWS Batch conformance job management."""

import json
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Pre-inject a fake boto3 module so submit_jobs() doesn't sys.exit(1)
if "boto3" not in sys.modules:
    sys.modules["boto3"] = types.ModuleType("boto3")

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "codec-conformance-eval" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

from aws_batch_conformance import submit_jobs, wait_for_jobs, fetch_job_result


class TestSubmitJobs:
    """Tests for submit_jobs()."""

    @pytest.fixture
    def base_config(self):
        return {
            "eval_name": "test-eval",
            "decoder": {"binary": "/app/decoder"},
            "execution": {
                "timeout_per_job": 120,
                "aws_batch": {
                    "region": "us-east-1",
                    "job_queue": "test-queue",
                    "job_definition": "test-job-def",
                    "s3_bucket": "test-bucket",
                },
            },
            "_resolved_streams": [
                {"name": "CABAC_A", "s3_path": "s3://bucket/CABAC_A.264", "source_id": "itu"},
                {"name": "INTER_B", "s3_path": "s3://bucket/INTER_B.264", "source_id": "itu"},
            ],
        }

    def test_submits_all_streams(self, base_config):
        mock_client = MagicMock()
        mock_client.submit_job.return_value = {"jobId": "job-123"}
        result = submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        assert len(result) == 2
        assert mock_client.submit_job.call_count == 2

    def test_job_info_fields(self, base_config):
        mock_client = MagicMock()
        mock_client.submit_job.return_value = {"jobId": "job-abc"}
        result = submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        job = result[0]
        assert job["job_id"] == "job-abc"
        assert job["stream_name"] == "CABAC_A"
        assert job["source_id"] == "itu"

    def test_no_resolved_streams_returns_empty(self, base_config):
        base_config["_resolved_streams"] = []
        mock_client = MagicMock()
        result = submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        assert result == []
        mock_client.submit_job.assert_not_called()

    def test_submit_error_captured(self, base_config):
        mock_client = MagicMock()
        mock_client.submit_job.side_effect = Exception("Throttled")
        result = submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        assert len(result) == 2
        assert result[0]["job_id"] is None
        assert "Throttled" in result[0]["error"]

    def test_job_name_sanitization(self, base_config):
        base_config["_resolved_streams"] = [
            {"name": "stream/v2@test#1", "s3_path": "s3://b/x", "source_id": "custom"},
        ]
        mock_client = MagicMock()
        mock_client.submit_job.return_value = {"jobId": "j1"}
        submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        call_kwargs = mock_client.submit_job.call_args
        job_name = call_kwargs.kwargs.get("jobName") or call_kwargs[1].get("jobName")
        # Job name should only contain [a-zA-Z0-9_-]
        assert re.match(r'^[a-zA-Z0-9_-]+$', job_name)

    def test_job_name_truncated_to_64(self, base_config):
        long_name = "A" * 200
        base_config["_resolved_streams"] = [
            {"name": long_name, "s3_path": "s3://b/x", "source_id": "long"},
        ]
        mock_client = MagicMock()
        mock_client.submit_job.return_value = {"jobId": "j2"}
        submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        call_kwargs = mock_client.submit_job.call_args
        job_name = call_kwargs.kwargs.get("jobName") or call_kwargs[1].get("jobName")
        # conf- prefix (5 chars) + 64 chars max from safe_name
        assert len(job_name) <= 69

    def test_default_priority_optional(self, base_config):
        base_config["_resolved_streams"] = [
            {"name": "test", "s3_path": "s3://b/x", "source_id": "s"},
        ]
        mock_client = MagicMock()
        mock_client.submit_job.return_value = {"jobId": "j3"}
        result = submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        assert result[0]["priority"] == "optional"

    def test_explicit_priority_preserved(self, base_config):
        base_config["_resolved_streams"] = [
            {"name": "test", "s3_path": "s3://b/x", "source_id": "s", "priority": "mandatory"},
        ]
        mock_client = MagicMock()
        mock_client.submit_job.return_value = {"jobId": "j4"}
        result = submit_jobs(base_config, "/tmp/out", batch_client=mock_client)
        assert result[0]["priority"] == "mandatory"


class TestWaitForJobs:
    """Tests for wait_for_jobs()."""

    def test_all_succeed(self):
        mock_client = MagicMock()
        mock_client.describe_jobs.return_value = {
            "jobs": [
                {"jobId": "j1", "status": "SUCCEEDED"},
                {"jobId": "j2", "status": "SUCCEEDED"},
            ]
        }
        jobs = [
            {"job_id": "j1", "stream_name": "A", "source_id": "s1"},
            {"job_id": "j2", "stream_name": "B", "source_id": "s2"},
        ]
        result = wait_for_jobs(mock_client, jobs, poll_interval=0, max_wait=10)
        assert len(result) == 2
        assert all(j["status"] == "success" for j in result)

    def test_mixed_success_and_failure(self):
        mock_client = MagicMock()
        mock_client.describe_jobs.return_value = {
            "jobs": [
                {"jobId": "j1", "status": "SUCCEEDED"},
                {"jobId": "j2", "status": "FAILED", "statusReason": "OOM"},
            ]
        }
        jobs = [
            {"job_id": "j1", "stream_name": "A", "source_id": "s1"},
            {"job_id": "j2", "stream_name": "B", "source_id": "s2"},
        ]
        result = wait_for_jobs(mock_client, jobs, poll_interval=0, max_wait=10)
        statuses = {j["stream_name"]: j["status"] for j in result}
        assert statuses["A"] == "success"
        assert statuses["B"] == "failed"

    def test_skips_null_job_ids(self):
        mock_client = MagicMock()
        mock_client.describe_jobs.return_value = {"jobs": []}
        jobs = [
            {"job_id": None, "stream_name": "A", "error": "submit failed"},
        ]
        result = wait_for_jobs(mock_client, jobs, poll_interval=0, max_wait=5)
        assert result == []

    def test_timeout_marks_pending_as_failed(self):
        mock_client = MagicMock()
        # Always return RUNNING — never completes
        mock_client.describe_jobs.return_value = {
            "jobs": [{"jobId": "j1", "status": "RUNNING"}]
        }
        jobs = [{"job_id": "j1", "stream_name": "A", "source_id": "s1"}]
        result = wait_for_jobs(mock_client, jobs, poll_interval=0, max_wait=0)
        assert len(result) == 1
        assert result[0]["status"] == "failed"
        assert "timeout" in result[0]["error"].lower()


class TestFetchJobResult:
    """Tests for fetch_job_result()."""

    def test_success(self):
        mock_s3 = MagicMock()
        body_data = json.dumps({"md5_decoded": "abc123", "decode_time_s": 2.5})
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=body_data.encode()))
        }
        result = fetch_job_result(mock_s3, "eval1", "stream_A", "my-bucket")
        assert result["md5_decoded"] == "abc123"
        assert result["decode_time_s"] == 2.5

    def test_not_found_returns_none(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        result = fetch_job_result(mock_s3, "eval1", "stream_A")
        assert result is None

    def test_s3_key_sanitized(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("test")
        fetch_job_result(mock_s3, "eval1", "stream/v2@test")
        call_kwargs = mock_s3.get_object.call_args
        key = call_kwargs.kwargs.get("Key") or call_kwargs[1].get("Key")
        # Key should not contain @ or raw /
        assert "@" not in key.split("/", 1)[-1].replace("_result.json", "")
