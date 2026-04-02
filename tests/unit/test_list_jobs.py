"""
Unit tests for list_jobs Lambda handler.

Tests Decimal serialization in response (HIGH-5).
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/jobs/list_jobs.py")
lambda_handler = _mod.lambda_handler


def _make_event(user_id="user-123", params=None):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "pathParameters": None,
        "queryStringParameters": params,
        "body": None,
    }


def _make_job_item(job_id="job-1", cost=Decimal("1.23"), budget=Decimal("10.0")):
    return {
        "job_id": job_id,
        "user_id": "user-123",
        "status": "COMPLETED",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T01:00:00",
        "records_generated": 100,
        "cost_estimate": cost,
        "budget_limit": budget,
    }


class TestListJobsDecimalSerialization:
    def setup_method(self):
        self.mock_table = MagicMock()
        _mod.jobs_table = self.mock_table

    def test_decimal_cost_values_serialize_correctly(self):
        """Decimal cost values from DynamoDB should not cause serialization errors."""
        self.mock_table.query.return_value = {
            "Items": [
                _make_job_item("job-1", Decimal("1.23456"), Decimal("50.0")),
                _make_job_item("job-2", Decimal("0"), Decimal("100.00")),
            ],
        }

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["jobs"]) == 2
        # Should not raise JSON serialization error
        # Values should be numeric (not strings or NaN)
        for job in body["jobs"]:
            assert isinstance(job["cost_estimate"], (int, float))
            assert isinstance(job["budget_limit"], (int, float))

    def test_nan_decimal_does_not_appear(self):
        """Ensure NaN-like Decimal values don't produce $NaN display."""
        self.mock_table.query.return_value = {
            "Items": [_make_job_item("job-1", Decimal("0"), Decimal("10.0"))],
        }

        response = lambda_handler(_make_event(), None)

        body_str = response["body"]
        assert "NaN" not in body_str
        assert "null" not in body_str.replace('"has_more": false', "")

    def test_string_cost_values_converted(self):
        """Cost values stored as strings in DynamoDB are handled."""
        item = _make_job_item("job-1")
        item["cost_estimate"] = "2.50"  # String, not Decimal
        item["budget_limit"] = "25.00"  # String, not Decimal

        self.mock_table.query.return_value = {"Items": [item]}

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        job = body["jobs"][0]
        # String cost_estimate should be converted to float
        assert job["cost_estimate"] == 2.5
        # String budget_limit should be converted to float
        assert job["budget_limit"] == 25.0
