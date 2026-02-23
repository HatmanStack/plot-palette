"""
Unit tests for quality scoring API endpoints.

Tests GET /jobs/{job_id}/quality and POST /jobs/{job_id}/quality handlers.
"""

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
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

_get_mod = load_handler("lambdas/quality/get_quality.py")
get_quality_handler = _get_mod.lambda_handler

_trigger_mod = load_handler("lambdas/quality/trigger_scoring.py")
trigger_scoring_handler = _trigger_mod.lambda_handler


def _make_event(
    method: str,
    path: str,
    path_params: dict | None = None,
    body: dict | None = None,
    user_id: str = "user-123",
) -> dict:
    """Build an API Gateway v2 event."""
    event: dict[str, Any] = {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": method, "path": path},
            "requestId": "req-001",
        },
        "pathParameters": path_params or {},
        "queryStringParameters": None,
        "body": json.dumps(body) if body else None,
    }
    return event


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset module-level mock clients before each test."""
    _get_mod.jobs_table = MagicMock()
    _get_mod.quality_table = MagicMock()

    _trigger_mod.jobs_table = MagicMock()
    _trigger_mod.quality_table = MagicMock()
    _trigger_mod.lambda_client = MagicMock()
    yield


@pytest.fixture
def quality_metrics_item():
    """A completed quality metrics DynamoDB item."""
    return {
        "job_id": "job-123",
        "scored_at": "2025-12-01T10:00:00",
        "sample_size": 20,
        "total_records": 100,
        "model_used_for_scoring": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "aggregate_scores": {
            "coherence": Decimal("0.85"),
            "relevance": Decimal("0.9"),
            "format_compliance": Decimal("0.95"),
        },
        "diversity_score": Decimal("0.75"),
        "overall_score": Decimal("0.86"),
        "record_scores": [
            {
                "record_index": 0,
                "coherence": 0.9,
                "relevance": 0.85,
                "format_compliance": 1.0,
                "detail": "Good record",
            }
        ],
        "scoring_cost": Decimal("0.05"),
        "status": "COMPLETED",
    }


class TestGetQuality:
    """Test GET /jobs/{job_id}/quality endpoint."""

    def test_get_quality_success(self, quality_metrics_item):
        """Mock scored job. Assert full metrics returned."""
        _get_mod.jobs_table.get_item.return_value = {
            "Item": {"job_id": "job-123", "user_id": "user-123", "status": "COMPLETED"}
        }
        _get_mod.quality_table.get_item.return_value = {"Item": quality_metrics_item}

        event = _make_event("GET", "/jobs/job-123/quality", {"job_id": "job-123"})
        response = get_quality_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["job_id"] == "job-123"
        assert body["overall_score"] == 0.86
        assert "aggregate_scores" in body
        assert body["status"] == "COMPLETED"

    def test_get_quality_not_scored(self):
        """No metrics exist. Assert 404."""
        _get_mod.jobs_table.get_item.return_value = {
            "Item": {"job_id": "job-123", "user_id": "user-123", "status": "COMPLETED"}
        }
        _get_mod.quality_table.get_item.return_value = {}

        event = _make_event("GET", "/jobs/job-123/quality", {"job_id": "job-123"})
        response = get_quality_handler(event, None)

        assert response["statusCode"] == 404

    def test_get_quality_not_owner(self):
        """Different user. Assert 403."""
        _get_mod.jobs_table.get_item.return_value = {
            "Item": {"job_id": "job-123", "user_id": "other-user", "status": "COMPLETED"}
        }

        event = _make_event("GET", "/jobs/job-123/quality", {"job_id": "job-123"}, user_id="user-123")
        response = get_quality_handler(event, None)

        assert response["statusCode"] == 403


class TestTriggerScoring:
    """Test POST /jobs/{job_id}/quality endpoint."""

    def test_trigger_scoring_success(self):
        """Mock COMPLETED job. Assert 202, Lambda invoked async."""
        _trigger_mod.jobs_table.get_item.return_value = {
            "Item": {"job_id": "job-123", "user_id": "user-123", "status": "COMPLETED"}
        }
        _trigger_mod.quality_table.get_item.return_value = {}

        event = _make_event("POST", "/jobs/job-123/quality", {"job_id": "job-123"})
        response = trigger_scoring_handler(event, None)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["job_id"] == "job-123"
        _trigger_mod.lambda_client.invoke.assert_called_once()
        invoke_kwargs = _trigger_mod.lambda_client.invoke.call_args[1]
        assert invoke_kwargs["InvocationType"] == "Event"

    def test_trigger_scoring_already_scored(self, quality_metrics_item):
        """Metrics exist with COMPLETED status. Assert 409."""
        _trigger_mod.jobs_table.get_item.return_value = {
            "Item": {"job_id": "job-123", "user_id": "user-123", "status": "COMPLETED"}
        }
        _trigger_mod.quality_table.get_item.return_value = {"Item": quality_metrics_item}

        event = _make_event("POST", "/jobs/job-123/quality", {"job_id": "job-123"})
        response = trigger_scoring_handler(event, None)

        assert response["statusCode"] == 409

    def test_trigger_scoring_not_completed(self):
        """Job is RUNNING. Assert 400."""
        _trigger_mod.jobs_table.get_item.return_value = {
            "Item": {"job_id": "job-123", "user_id": "user-123", "status": "RUNNING"}
        }

        event = _make_event("POST", "/jobs/job-123/quality", {"job_id": "job-123"})
        response = trigger_scoring_handler(event, None)

        assert response["statusCode"] == 400
