"""
Unit tests for batch job creation Lambda handler.
"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/jobs/create_batch.py")
lambda_handler = _mod.lambda_handler


def _make_event(body: dict, user_id: str = "user-123") -> dict:
    """Build an API Gateway v2 event for POST /jobs/batch."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "POST", "path": "/jobs/batch"},
            "requestId": "req-001",
        },
        "body": json.dumps(body),
    }


def _base_body(**overrides) -> dict:
    """Return a valid batch creation request body."""
    body = {
        "name": "A/B test: model comparison",
        "template_id": "tmpl-123",
        "template_version": 1,
        "seed_data_path": "seed-data/user-123/data.json",
        "base_config": {
            "budget_limit": 10.0,
            "num_records": 100,
            "output_format": "JSONL",
        },
        "sweep": {"model_tier": ["tier-1", "tier-2", "tier-3"]},
    }
    body.update(overrides)
    return body


class TestCreateBatch:
    """Tests for create_batch Lambda handler."""

    def setup_method(self):
        """Reset mocks before each test."""
        self.mock_jobs = MagicMock()
        self.mock_templates = MagicMock()
        self.mock_batches = MagicMock()
        self.mock_sfn = MagicMock()

        _mod.jobs_table = self.mock_jobs
        _mod.templates_table = self.mock_templates
        _mod.batches_table = self.mock_batches
        _mod.sfn_client = self.mock_sfn

        # Default: template exists
        self.mock_templates.get_item.return_value = {
            "Item": {"template_id": "tmpl-123", "version": 1, "user_id": "user-123"}
        }
        # Default: SFN succeeds
        self.mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123:execution:sm:job-test",
            "startDate": datetime.now(UTC),
        }

    def test_batch_create_model_sweep(self):
        """Sweep 3 model tiers creates 3 jobs and 3 SFN executions."""
        response = lambda_handler(_make_event(_base_body()), None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["job_count"] == 3
        assert len(body["job_ids"]) == 3
        assert "batch_id" in body
        assert self.mock_sfn.start_execution.call_count == 3
        assert self.mock_jobs.put_item.call_count == 3
        assert self.mock_batches.put_item.call_count == 1

    def test_batch_create_seed_data_sweep(self):
        """Sweep 2 seed files creates 2 jobs."""
        body = _base_body(
            sweep={"seed_data_path": ["seed-data/user-123/a.json", "seed-data/user-123/b.json"]}
        )
        response = lambda_handler(_make_event(body), None)

        assert response["statusCode"] == 201
        result = json.loads(response["body"])
        assert result["job_count"] == 2

    def test_batch_exceeds_max_size(self):
        """25 sweep values exceed MAX_BATCH_SIZE, returns 400."""
        body = _base_body(sweep={"num_records": list(range(1, 26))})
        response = lambda_handler(_make_event(body), None)

        assert response["statusCode"] == 400
        assert "MAX_BATCH_SIZE" in json.loads(response["body"])["error"]

    def test_batch_template_not_found(self):
        """Invalid template_id returns 404."""
        self.mock_templates.get_item.return_value = {}

        response = lambda_handler(_make_event(_base_body()), None)
        assert response["statusCode"] == 404

    def test_batch_partial_failure(self):
        """If 1 SFN start fails, batch still created with successful jobs."""
        self.mock_sfn.start_execution.side_effect = [
            {
                "executionArn": "arn:aws:states:us-east-1:123:execution:sm:job-1",
                "startDate": datetime.now(UTC),
            },
            Exception("SFN failure"),
            {
                "executionArn": "arn:aws:states:us-east-1:123:execution:sm:job-3",
                "startDate": datetime.now(UTC),
            },
        ]

        response = lambda_handler(_make_event(_base_body()), None)

        assert response["statusCode"] == 201
        result = json.loads(response["body"])
        assert result["job_count"] == 2
        assert len(result["failed_jobs"]) == 1
        assert self.mock_batches.put_item.call_count == 1

    def test_batch_stores_sweep_config(self):
        """Assert sweep_config stored in batch record."""
        lambda_handler(_make_event(_base_body()), None)

        # Check the batch item put into DynamoDB
        batch_item = self.mock_batches.put_item.call_args[1]["Item"]
        assert "model_tier" in batch_item["sweep_config"]

    def test_batch_single_sweep_dimension(self):
        """Reject requests with 2 sweep keys."""
        body = _base_body(
            sweep={
                "model_tier": ["tier-1", "tier-2"],
                "num_records": [100, 200],
            }
        )
        response = lambda_handler(_make_event(body), None)

        assert response["statusCode"] == 400
        assert "single sweep dimension" in json.loads(response["body"])["error"].lower()
