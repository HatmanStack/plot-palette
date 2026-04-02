"""
Unit tests for stream_progress Lambda handler.

Tests SSE-formatted responses for job progress streaming.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from tests.unit.handler_import import load_handler

pytestmark = pytest.mark.unit

_mod = load_handler("lambdas/jobs/stream_progress.py")
lambda_handler = _mod.lambda_handler


def _make_event(user_id="user-123", job_id="job-456"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "pathParameters": {"job_id": job_id},
        "queryStringParameters": None,
        "body": None,
    }


def _make_job(job_id="job-456", user_id="user-123", status="RUNNING"):
    return {
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "records_generated": 150,
        "tokens_used": 7500,
        "cost_estimate": Decimal("1.23"),
        "budget_limit": Decimal("10.0"),
        "updated_at": "2026-02-22T12:00:00+00:00",
    }


class TestStreamProgress:
    def setup_method(self):
        self.mock_table = MagicMock()
        _mod.jobs_table = self.mock_table

    def test_stream_running_job(self):
        """Mock RUNNING job. Assert SSE data event with progress fields."""
        self.mock_table.get_item.return_value = {"Item": _make_job()}

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 200
        body = response["body"]
        assert "data:" in body
        # Should NOT have event: complete for running job
        assert "event: complete" not in body

        # Parse the data line
        data_line = [l for l in body.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[5:].strip())
        assert data["job_id"] == "job-456"
        assert data["status"] == "RUNNING"
        assert data["records_generated"] == 150
        assert data["tokens_used"] == 7500
        assert data["cost_estimate"] == 1.23

    def test_stream_completed_job(self):
        """Mock COMPLETED job. Assert event: complete."""
        self.mock_table.get_item.return_value = {
            "Item": _make_job(status="COMPLETED")
        }

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 200
        body = response["body"]
        assert "event: complete" in body
        assert "data:" in body

    def test_stream_not_owner(self):
        """Different user_id. Assert 403."""
        self.mock_table.get_item.return_value = {
            "Item": _make_job(user_id="other-user")
        }

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 403

    def test_stream_not_found(self):
        """Nonexistent job. Assert 404."""
        self.mock_table.get_item.return_value = {}

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 404

    def test_stream_content_type(self):
        """Assert Content-Type is text/event-stream."""
        self.mock_table.get_item.return_value = {"Item": _make_job()}

        response = lambda_handler(_make_event(), None)

        assert response["headers"]["Content-Type"] == "text/event-stream"

    def test_stream_cache_control(self):
        """Assert Cache-Control: no-cache header."""
        self.mock_table.get_item.return_value = {"Item": _make_job()}

        response = lambda_handler(_make_event(), None)

        assert response["headers"]["Cache-Control"] == "no-cache"

    def test_missing_path_parameters_returns_400(self):
        """Missing pathParameters key entirely returns 400, not 500."""
        event = _make_event()
        del event["pathParameters"]

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    def test_null_path_parameters_returns_400(self):
        """pathParameters set to None returns 400, not 500."""
        event = _make_event()
        event["pathParameters"] = None

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    def test_missing_job_id_in_path_parameters_returns_400(self):
        """pathParameters present but missing job_id returns 400."""
        event = _make_event()
        event["pathParameters"] = {}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    def test_missing_jwt_claims_returns_401(self):
        """Missing JWT claims returns 401, not 500."""
        event = {
            "requestContext": {"requestId": "test-req-1"},
            "pathParameters": {"job_id": "job-456"},
            "queryStringParameters": None,
            "body": None,
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 401

    def test_decimal_values_serialize_to_float(self):
        """DynamoDB Decimal values are correctly converted to float in response."""
        job = _make_job()
        job["cost_estimate"] = Decimal("0.00123456789")
        job["budget_limit"] = Decimal("999.99")
        self.mock_table.get_item.return_value = {"Item": job}

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 200
        data_line = [line for line in response["body"].split("\n") if line.startswith("data:")][0]
        data = json.loads(data_line[5:].strip())
        assert isinstance(data["cost_estimate"], float)
        assert isinstance(data["budget_limit"], float)
        assert abs(data["cost_estimate"] - 0.00123456789) < 1e-9
        assert abs(data["budget_limit"] - 999.99) < 1e-9

    def test_missing_cost_fields_default_to_zero(self):
        """Missing cost fields default to 0.0 float, not None."""
        job = {
            "job_id": "job-456",
            "user_id": "user-123",
            "status": "QUEUED",
            "records_generated": 0,
            "tokens_used": 0,
            "updated_at": "2026-01-01T00:00:00",
        }
        self.mock_table.get_item.return_value = {"Item": job}

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 200
        data_line = [line for line in response["body"].split("\n") if line.startswith("data:")][0]
        data = json.loads(data_line[5:].strip())
        assert data["cost_estimate"] == 0.0
        assert data["budget_limit"] == 0.0

    def test_dynamodb_error_returns_500(self):
        """DynamoDB error returns 500 with logging."""
        from botocore.exceptions import ClientError

        self.mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DDB error"}},
            "GetItem",
        )

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 500
