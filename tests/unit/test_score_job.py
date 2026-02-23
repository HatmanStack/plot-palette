"""
Unit tests for quality scoring Lambda handler.

Tests the score_job handler that samples records from completed jobs,
sends them to an LLM for evaluation, and stores quality metrics.
"""

import json
import os
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JOBS_TABLE_NAME", "test-Jobs")
os.environ.setdefault("TEMPLATES_TABLE_NAME", "test-Templates")
os.environ.setdefault("QUALITY_METRICS_TABLE_NAME", "test-QualityMetrics")
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("ALLOWED_ORIGIN", "http://localhost:3000")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from tests.unit.handler_import import load_handler

# Also need to mock bedrock client during load
_bedrock_mock = MagicMock()
with patch("shared.aws_clients.get_bedrock_client", return_value=_bedrock_mock):
    _mod = load_handler("lambdas/quality/score_job.py")
lambda_handler = _mod.lambda_handler


def _make_jsonl_body(records: list[dict[str, Any]]) -> bytes:
    """Create a JSONL byte stream from a list of dicts."""
    lines = [json.dumps(r) for r in records]
    return "\n".join(lines).encode("utf-8")


def _make_scoring_response(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a mock Bedrock response containing JSON scoring results."""
    body_stream = MagicMock()
    body_stream.read.return_value = json.dumps(
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(scores),
                }
            ]
        }
    ).encode("utf-8")
    return {"body": body_stream}


def _default_score(index: int = 0) -> dict[str, Any]:
    return {
        "coherence": 0.9,
        "relevance": 0.85,
        "format_compliance": 0.95,
        "detail": f"Record {index} looks good",
    }


def _make_batch_scores(count: int, start_index: int = 0) -> list[dict[str, Any]]:
    """Create a batch of score dicts."""
    return [_default_score(start_index + i) for i in range(count)]


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset module-level mock clients before each test."""
    _mod.jobs_table = MagicMock()
    _mod.templates_table = MagicMock()
    _mod.quality_table = MagicMock()
    _mod.s3_client = MagicMock()
    _mod.bedrock_client = MagicMock()
    yield


@pytest.fixture
def completed_job_item():
    """A completed job DynamoDB item."""
    return {
        "job_id": "job-123",
        "user_id": "user-456",
        "status": "COMPLETED",
        "config": {
            "template_id": "tmpl-789",
            "template_version": 1,
            "output_format": "JSONL",
        },
        "records_generated": 50,
        "budget_limit": 10,
        "cost_estimate": 5,
    }


@pytest.fixture
def template_item():
    """A template DynamoDB item."""
    return {
        "template_id": "tmpl-789",
        "version": 1,
        "name": "Test Template",
        "schema_requirements": ["author.name", "poem.text"],
    }


@pytest.fixture
def sample_records():
    """50 sample JSONL records."""
    return [
        {
            "seed_data_id": f"seed-{i}",
            "generation_result": f"Generated text for record {i} with unique content about topic {i}",
        }
        for i in range(50)
    ]


class TestScoreJobSuccess:
    """Test successful quality scoring flow."""

    def test_score_job_success(self, completed_job_item, template_item, sample_records):
        """Mock S3 export with 50 records, mock Bedrock scoring responses. Assert QualityMetrics stored."""
        _mod.jobs_table.get_item.return_value = {"Item": completed_job_item}
        _mod.templates_table.get_item.return_value = {"Item": template_item}

        _mod.s3_client.get_object.return_value = {
            "Body": BytesIO(_make_jsonl_body(sample_records))
        }

        _mod.bedrock_client.invoke_model.side_effect = [
            _make_scoring_response(_make_batch_scores(5, i * 5)) for i in range(4)
        ]

        result = lambda_handler({"job_id": "job-123"}, None)

        # Assert quality metrics were stored (final put_item call = COMPLETED)
        assert _mod.quality_table.put_item.call_count >= 1
        last_call = _mod.quality_table.put_item.call_args_list[-1]
        stored_item = last_call[1]["Item"]
        assert stored_item["status"] == "COMPLETED"
        assert stored_item["sample_size"] == 20
        assert "coherence" in stored_item["aggregate_scores"]

    def test_score_job_samples_correctly(self, template_item):
        """1000 records, sample_size=20. Assert only 4 Bedrock calls (5 per batch)."""
        records = [{"generation_result": f"Record {i}", "seed_data_id": f"s{i}"} for i in range(1000)]

        _mod.jobs_table.get_item.return_value = {
            "Item": {
                "job_id": "job-big",
                "user_id": "user-1",
                "status": "COMPLETED",
                "config": {"template_id": "tmpl-789", "template_version": 1, "output_format": "JSONL"},
                "records_generated": 1000,
                "budget_limit": 50,
                "cost_estimate": 20,
            }
        }
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.return_value = {"Body": BytesIO(_make_jsonl_body(records))}

        _mod.bedrock_client.invoke_model.side_effect = [
            _make_scoring_response(_make_batch_scores(5, i * 5)) for i in range(4)
        ]

        lambda_handler({"job_id": "job-big"}, None)

        assert _mod.bedrock_client.invoke_model.call_count == 4

    def test_score_job_diversity_calculation(self, template_item):
        """20 records, 15 unique prefixes. Assert diversity=0.75."""
        # Create 20 records where 15 have unique first-50-char prefixes
        records = []
        for i in range(15):
            records.append({"generation_result": f"Unique content number {i:03d} " + "x" * 40, "seed_data_id": f"s{i}"})
        for i in range(5):
            # Duplicate prefix of record 0
            records.append({"generation_result": records[0]["generation_result"], "seed_data_id": f"dup{i}"})

        _mod.jobs_table.get_item.return_value = {
            "Item": {
                "job_id": "job-div",
                "user_id": "user-1",
                "status": "COMPLETED",
                "config": {"template_id": "tmpl-789", "template_version": 1, "output_format": "JSONL"},
                "records_generated": 20,
                "budget_limit": 10,
                "cost_estimate": 5,
            }
        }
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.return_value = {"Body": BytesIO(_make_jsonl_body(records))}

        _mod.bedrock_client.invoke_model.side_effect = [
            _make_scoring_response(_make_batch_scores(5, i * 5)) for i in range(4)
        ]

        lambda_handler({"job_id": "job-div"}, None)

        stored_item = _mod.quality_table.put_item.call_args_list[-1][1]["Item"]
        # All 20 records are sampled (20 <= QUALITY_SAMPLE_SIZE=20)
        # 15 unique prefixes out of 20
        assert float(stored_item["diversity_score"]) == pytest.approx(0.75, abs=0.01)


class TestScoreJobFailures:
    """Test failure scenarios for quality scoring."""

    def test_score_job_partial_failure(self, completed_job_item, template_item, sample_records):
        """3 of 4 batch calls fail. Assert FAILED status (>50% records fail)."""
        _mod.jobs_table.get_item.return_value = {"Item": completed_job_item}
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.return_value = {"Body": BytesIO(_make_jsonl_body(sample_records))}

        # First batch succeeds, next 3 fail
        _mod.bedrock_client.invoke_model.side_effect = [
            _make_scoring_response(_make_batch_scores(5, 0)),
            Exception("Bedrock timeout"),
            Exception("Bedrock throttle"),
            Exception("Bedrock error"),
        ]

        lambda_handler({"job_id": "job-123"}, None)

        stored_item = _mod.quality_table.put_item.call_args_list[-1][1]["Item"]
        # 15/20 = 75% failed -> FAILED
        assert stored_item["status"] == "FAILED"

    def test_score_job_majority_failure(self, completed_job_item, template_item, sample_records):
        """All 4 batches fail. Assert FAILED status."""
        _mod.jobs_table.get_item.return_value = {"Item": completed_job_item}
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.return_value = {"Body": BytesIO(_make_jsonl_body(sample_records))}

        _mod.bedrock_client.invoke_model.side_effect = Exception("All calls fail")

        lambda_handler({"job_id": "job-123"}, None)

        stored_item = _mod.quality_table.put_item.call_args_list[-1][1]["Item"]
        assert stored_item["status"] == "FAILED"

    def test_score_job_not_completed(self):
        """Job status is RUNNING. Assert no quality metrics stored."""
        _mod.jobs_table.get_item.return_value = {
            "Item": {
                "job_id": "job-run",
                "user_id": "user-1",
                "status": "RUNNING",
                "config": {},
                "records_generated": 10,
                "budget_limit": 10,
                "cost_estimate": 5,
            }
        }

        result = lambda_handler({"job_id": "job-run"}, None)

        # Should not store quality metrics
        _mod.quality_table.put_item.assert_not_called()
        assert "error" in result

    def test_score_job_no_export(self, completed_job_item, template_item):
        """S3 file doesn't exist. Assert FAILED with error message."""
        from botocore.exceptions import ClientError

        _mod.jobs_table.get_item.return_value = {"Item": completed_job_item}
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
        )

        lambda_handler({"job_id": "job-123"}, None)

        stored_item = _mod.quality_table.put_item.call_args_list[-1][1]["Item"]
        assert stored_item["status"] == "FAILED"
        assert "error_message" in stored_item


class TestScoreJobBatching:
    """Test batched scoring prompts."""

    def test_score_job_batched_prompts(self, completed_job_item, template_item, sample_records):
        """Assert Bedrock called 4 times (5 records per batch) not 20."""
        _mod.jobs_table.get_item.return_value = {"Item": completed_job_item}
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.return_value = {"Body": BytesIO(_make_jsonl_body(sample_records))}

        _mod.bedrock_client.invoke_model.side_effect = [
            _make_scoring_response(_make_batch_scores(5, i * 5)) for i in range(4)
        ]

        lambda_handler({"job_id": "job-123"}, None)

        # 20 records / 5 per batch = 4 calls
        assert _mod.bedrock_client.invoke_model.call_count == 4

    def test_score_job_cost_tracking(self, completed_job_item, template_item, sample_records):
        """Assert scoring_cost is calculated from token usage."""
        _mod.jobs_table.get_item.return_value = {"Item": completed_job_item}
        _mod.templates_table.get_item.return_value = {"Item": template_item}
        _mod.s3_client.get_object.return_value = {"Body": BytesIO(_make_jsonl_body(sample_records))}

        _mod.bedrock_client.invoke_model.side_effect = [
            _make_scoring_response(_make_batch_scores(5, i * 5)) for i in range(4)
        ]

        lambda_handler({"job_id": "job-123"}, None)

        stored_item = _mod.quality_table.put_item.call_args_list[-1][1]["Item"]
        # scoring_cost should be > 0 (estimated from prompt + response tokens)
        assert float(stored_item["scoring_cost"]) > 0
