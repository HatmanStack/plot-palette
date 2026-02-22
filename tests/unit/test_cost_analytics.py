"""
Plot Palette - Cost Analytics Lambda Unit Tests

Tests for GET /dashboard/cost-analytics endpoint that aggregates
cost data across user jobs by day, week, or model.
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

# Load the actual handler module
_mod = load_handler("lambdas/dashboard/get_cost_analytics.py")
lambda_handler = _mod.lambda_handler


def make_event(
    user_id: str = "test-user-123",
    period: str | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Build an API Gateway v2 event for cost analytics."""
    params: dict[str, str] = {}
    if period:
        params["period"] = period
    if group_by:
        params["group_by"] = group_by

    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "GET", "path": "/dashboard/cost-analytics"},
            "requestId": "test-request-id",
        },
        "queryStringParameters": params or None,
        "body": None,
    }


def make_job_item(
    job_id: str,
    user_id: str = "test-user-123",
    status: str = "COMPLETED",
    budget_limit: float = 100.0,
    records_generated: int = 100,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a DynamoDB job item (high-level Table format)."""
    return {
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "budget_limit": Decimal(str(budget_limit)),
        "records_generated": records_generated,
        "cost_estimate": Decimal("0"),
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "config": {"template_id": "tmpl-1", "num_records": records_generated},
    }


def make_cost_record(
    job_id: str,
    timestamp: str,
    bedrock: float = 1.0,
    fargate: float = 0.5,
    s3: float = 0.1,
    model_id: str = "meta.llama3-1-8b-instruct-v1:0",
) -> dict[str, Any]:
    """Create a DynamoDB cost tracking item (high-level Table format)."""
    total = bedrock + fargate + s3
    return {
        "job_id": job_id,
        "timestamp": timestamp,
        "estimated_cost": {
            "bedrock": Decimal(str(bedrock)),
            "fargate": Decimal(str(fargate)),
            "s3": Decimal(str(s3)),
            "total": Decimal(str(round(total, 4))),
        },
        "model_id": model_id,
        "bedrock_tokens": 10000,
        "fargate_hours": Decimal("0.1"),
        "s3_operations": 50,
    }


def _invoke(event, jobs_items, cost_records_by_job):
    """Invoke lambda_handler with mocked DynamoDB tables."""
    mock_jobs_table = MagicMock()
    mock_jobs_table.query.return_value = {"Items": jobs_items}

    mock_cost_table = MagicMock()

    def cost_query(**kwargs):
        # Extract job_id from the boto3 Key condition expression object
        expr = kwargs.get("KeyConditionExpression")
        if expr is not None:
            # Dig into the condition object's internal values
            try:
                values = expr.get_expression().get("values", ())
                if len(values) >= 2:
                    job_id_val = values[1]
                    if job_id_val in cost_records_by_job:
                        return {"Items": cost_records_by_job[job_id_val]}
            except (AttributeError, IndexError):
                pass
        return {"Items": []}

    mock_cost_table.query.side_effect = cost_query

    _mod.jobs_table = mock_jobs_table
    _mod.cost_tracking_table = mock_cost_table

    return lambda_handler(event, None)


class TestCostAnalyticsByDay:
    """Test daily aggregation of cost data."""

    def test_cost_analytics_by_day(self):
        """Mock 3 jobs with cost records across 5 days. Assert daily totals."""
        now = datetime.now(UTC)
        jobs = [
            make_job_item("job-1", created_at=(now - timedelta(days=5)).isoformat()),
            make_job_item("job-2", created_at=(now - timedelta(days=3)).isoformat()),
            make_job_item("job-3", created_at=(now - timedelta(days=1)).isoformat()),
        ]

        day1 = (now - timedelta(days=5)).isoformat()
        day2 = (now - timedelta(days=4)).isoformat()
        day3 = (now - timedelta(days=3)).isoformat()
        day4 = (now - timedelta(days=2)).isoformat()
        day5 = (now - timedelta(days=1)).isoformat()

        cost_records = {
            "job-1": [
                make_cost_record("job-1", day1, bedrock=1.0, fargate=0.5, s3=0.1),
                make_cost_record("job-1", day2, bedrock=2.0, fargate=0.3, s3=0.05),
            ],
            "job-2": [
                make_cost_record("job-2", day3, bedrock=1.5, fargate=0.4, s3=0.08),
            ],
            "job-3": [
                make_cost_record("job-3", day4, bedrock=0.8, fargate=0.2, s3=0.03),
                make_cost_record("job-3", day5, bedrock=3.0, fargate=1.0, s3=0.2),
            ],
        }

        response = _invoke(make_event(period="30d", group_by="day"), jobs, cost_records)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "time_series" in body
        assert "summary" in body
        assert len(body["time_series"]) == 5

        # Verify total spend sums correctly
        total = body["summary"]["total_spend"]
        expected = (1.6) + (2.35) + (1.98) + (1.03) + (4.2)
        assert abs(total - expected) < 0.01


class TestCostAnalyticsByModel:
    """Test model-based aggregation."""

    def test_cost_analytics_by_model(self):
        """Mock cost records with different model_ids. Assert per-model sums."""
        now = datetime.now(UTC)
        jobs = [make_job_item("job-1", created_at=(now - timedelta(days=5)).isoformat())]

        cost_records = {
            "job-1": [
                make_cost_record("job-1", (now - timedelta(days=3)).isoformat(),
                                 bedrock=1.0, fargate=0.5, s3=0.1,
                                 model_id="meta.llama3-1-8b-instruct-v1:0"),
                make_cost_record("job-1", (now - timedelta(days=2)).isoformat(),
                                 bedrock=5.0, fargate=0.5, s3=0.1,
                                 model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"),
                make_cost_record("job-1", (now - timedelta(days=1)).isoformat(),
                                 bedrock=2.0, fargate=0.3, s3=0.05,
                                 model_id="meta.llama3-1-8b-instruct-v1:0"),
            ],
        }

        response = _invoke(make_event(group_by="model"), jobs, cost_records)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "by_model" in body
        assert len(body["by_model"]) == 2

        # Check llama total: (1.0+0.5+0.1) + (2.0+0.3+0.05) = 3.95
        llama = next(m for m in body["by_model"] if "llama" in m["model_id"].lower())
        assert abs(llama["total"] - 3.95) < 0.01
        assert llama["model_name"] == "Llama 3.1 8B"

        # Check claude total: (5.0+0.5+0.1) = 5.6
        claude = next(m for m in body["by_model"] if "claude" in m["model_id"].lower())
        assert abs(claude["total"] - 5.6) < 0.01
        assert claude["model_name"] == "Claude 3.5 Sonnet"


class TestCostAnalyticsSummary:
    """Test summary statistics calculation."""

    def test_cost_analytics_summary(self):
        """Assert avg_cost_per_job, budget_efficiency calculated correctly."""
        now = datetime.now(UTC)
        jobs = [
            make_job_item("job-1", budget_limit=50.0, records_generated=100,
                          created_at=(now - timedelta(days=5)).isoformat()),
            make_job_item("job-2", budget_limit=100.0, records_generated=200,
                          created_at=(now - timedelta(days=3)).isoformat()),
        ]

        cost_records = {
            "job-1": [make_cost_record("job-1", (now - timedelta(days=4)).isoformat(),
                                       bedrock=10.0, fargate=2.0, s3=0.5)],
            "job-2": [make_cost_record("job-2", (now - timedelta(days=2)).isoformat(),
                                       bedrock=20.0, fargate=4.0, s3=1.0)],
        }

        response = _invoke(make_event(), jobs, cost_records)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        summary = body["summary"]

        # Total spend: 12.5 + 25.0 = 37.5
        assert abs(summary["total_spend"] - 37.5) < 0.01
        assert summary["job_count"] == 2
        # Avg cost per job: 37.5 / 2 = 18.75
        assert abs(summary["avg_cost_per_job"] - 18.75) < 0.01
        # Avg cost per record: 37.5 / 300 = 0.125
        assert abs(summary["avg_cost_per_record"] - 0.125) < 0.01
        # Budget efficiency: (12.5/50 + 25/100) / 2 = (0.25 + 0.25) / 2 = 0.25
        assert abs(summary["budget_efficiency"] - 0.25) < 0.01


class TestCostAnalyticsEmpty:
    """Test empty data handling."""

    def test_cost_analytics_empty(self):
        """User with no jobs. Assert empty arrays and zero stats."""
        response = _invoke(make_event(), [], {})

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["summary"]["total_spend"] == 0
        assert body["summary"]["job_count"] == 0
        assert body["summary"]["avg_cost_per_job"] == 0
        assert body["summary"]["avg_cost_per_record"] == 0
        assert body["time_series"] == []
        assert body["by_model"] == []


class TestCostAnalyticsPeriodFilter:
    """Test period filtering."""

    def test_cost_analytics_period_filter(self):
        """Assert 7d period returns only recent jobs from the query."""
        now = datetime.now(UTC)
        # The handler uses GSI key condition to filter by created_at >= cutoff
        # So only recent jobs would be returned by DynamoDB
        recent_jobs = [
            make_job_item("job-recent", created_at=(now - timedelta(days=2)).isoformat()),
        ]

        cost_records = {
            "job-recent": [
                make_cost_record("job-recent", (now - timedelta(days=1)).isoformat(),
                                 bedrock=5.0, fargate=1.0, s3=0.2),
            ],
        }

        response = _invoke(make_event(period="7d"), recent_jobs, cost_records)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["summary"]["job_count"] == 1
        assert abs(body["summary"]["total_spend"] - 6.2) < 0.01


class TestCostAnalyticsCap:
    """Test job cap at 100."""

    def test_cost_analytics_caps_at_100_jobs(self):
        """Mock 150 jobs, assert only 100 processed (handler caps via [:100])."""
        now = datetime.now(UTC)
        jobs = [
            make_job_item(f"job-{i}", created_at=(now - timedelta(days=1)).isoformat())
            for i in range(150)
        ]

        # Only return first 100 from the mock (simulating the handler cap)
        mock_jobs_table = MagicMock()
        mock_jobs_table.query.return_value = {"Items": jobs}

        mock_cost_table = MagicMock()
        mock_cost_table.query.return_value = {"Items": []}

        _mod.jobs_table = mock_jobs_table
        _mod.cost_tracking_table = mock_cost_table

        response = lambda_handler(make_event(), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # The handler caps at MAX_JOBS (100), so cost table queried <= 100 times
        assert mock_cost_table.query.call_count <= 100
        assert body["summary"]["job_count"] <= 100
