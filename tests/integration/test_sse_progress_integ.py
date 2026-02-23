"""
Integration tests for SSE progress streaming — calls actual lambda_handler against moto.

Uses moto's @mock_aws to create real DynamoDB tables, then invokes the
actual stream_progress.lambda_handler.
"""

import json
from decimal import Decimal

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/jobs/stream_progress.py")
lambda_handler = _mod.lambda_handler


def _create_jobs_table(dynamodb):
    """Create Jobs table."""
    return dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _make_event(user_id="user-A", job_id="job-1"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "pathParameters": {"job_id": job_id},
        "queryStringParameters": None,
        "body": None,
    }


@mock_aws
def test_sse_running_job_returns_data_event():
    """RUNNING job returns SSE data event with progress fields."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)

    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "RUNNING",
        "records_generated": 150,
        "tokens_used": 7500,
        "cost_estimate": Decimal("1.23"),
        "budget_limit": Decimal("10.0"),
        "updated_at": "2026-02-22T12:00:00",
    })

    _mod.jobs_table = jobs_table

    result = lambda_handler(_make_event(), None)

    assert result["statusCode"] == 200
    assert result["headers"]["Content-Type"] == "text/event-stream"
    assert result["headers"]["Cache-Control"] == "no-cache"

    # Parse SSE body
    body = result["body"]
    lines = body.strip().split("\n")

    # No event: line for non-terminal (just data:)
    assert not any(line.startswith("event:") for line in lines)

    data_line = next(line for line in lines if line.startswith("data:"))
    data = json.loads(data_line[len("data: "):])
    assert data["job_id"] == "job-1"
    assert data["status"] == "RUNNING"
    assert data["records_generated"] == 150
    assert data["tokens_used"] == 7500
    assert data["cost_estimate"] == 1.23
    assert data["budget_limit"] == 10.0


@mock_aws
def test_sse_completed_job_returns_complete_event():
    """COMPLETED job returns SSE event: complete signal."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)

    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "COMPLETED",
        "records_generated": 500,
        "tokens_used": 25000,
        "cost_estimate": Decimal("5.00"),
        "budget_limit": Decimal("10.0"),
        "updated_at": "2026-02-22T13:00:00",
    })

    _mod.jobs_table = jobs_table

    result = lambda_handler(_make_event(), None)

    assert result["statusCode"] == 200

    body = result["body"]
    lines = body.strip().split("\n")

    # Should have event: complete line
    assert any(line.strip() == "event: complete" for line in lines)

    data_line = next(line for line in lines if line.startswith("data:"))
    data = json.loads(data_line[len("data: "):])
    assert data["status"] == "COMPLETED"
    assert data["records_generated"] == 500


@mock_aws
def test_sse_not_found():
    """Nonexistent job returns 404."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)

    _mod.jobs_table = jobs_table

    result = lambda_handler(_make_event(job_id="nonexistent"), None)

    assert result["statusCode"] == 404


@mock_aws
def test_sse_not_owner():
    """Different user attempting to stream returns 403."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)

    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "RUNNING",
        "records_generated": 100,
    })

    _mod.jobs_table = jobs_table

    result = lambda_handler(_make_event(user_id="user-B", job_id="job-1"), None)

    assert result["statusCode"] == 403


@mock_aws
def test_sse_failed_job_returns_complete_event():
    """FAILED job also returns event: complete (terminal state)."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)

    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "FAILED",
        "records_generated": 50,
        "tokens_used": 2000,
        "cost_estimate": Decimal("0.50"),
        "budget_limit": Decimal("10.0"),
        "updated_at": "2026-02-22T14:00:00",
    })

    _mod.jobs_table = jobs_table

    result = lambda_handler(_make_event(), None)

    assert result["statusCode"] == 200

    body = result["body"]
    assert "event: complete" in body

    data_line = next(
        line for line in body.strip().split("\n") if line.startswith("data:")
    )
    data = json.loads(data_line[len("data: "):])
    assert data["status"] == "FAILED"


@mock_aws
def test_sse_budget_exceeded_returns_complete_event():
    """BUDGET_EXCEEDED job returns event: complete (terminal state)."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)

    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "BUDGET_EXCEEDED",
        "records_generated": 200,
        "tokens_used": 10000,
        "cost_estimate": Decimal("10.01"),
        "budget_limit": Decimal("10.0"),
        "updated_at": "2026-02-22T15:00:00",
    })

    _mod.jobs_table = jobs_table

    result = lambda_handler(_make_event(), None)

    assert result["statusCode"] == 200

    body = result["body"]
    assert "event: complete" in body

    data_line = next(
        line for line in body.strip().split("\n") if line.startswith("data:")
    )
    data = json.loads(data_line[len("data: "):])
    assert data["status"] == "BUDGET_EXCEEDED"
