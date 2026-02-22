"""
Integration tests for cost analytics — calls actual lambda_handler against moto.

Uses moto's @mock_aws to create real DynamoDB tables, then invokes the
actual get_cost_analytics.lambda_handler.
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/dashboard/get_cost_analytics.py")
lambda_handler = _mod.lambda_handler


def _make_event(user_id="user-A", period="30d", group_by="day"):
    params = {"period": period, "group_by": group_by}
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "queryStringParameters": params,
        "body": None,
    }


@mock_aws
def test_cost_analytics_user_isolation():
    """
    Create jobs for user A and user B. Invoke as user A.
    Verify only user A's data returned.
    """
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    now = datetime.now(UTC)

    # Create Jobs table with GSI
    jobs_table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-id-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create CostTracking table
    cost_table = dynamodb.create_table(
        TableName="plot-palette-CostTracking-test",
        KeySchema=[
            {"AttributeName": "job_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Insert jobs for user A
    for i in range(3):
        jobs_table.put_item(Item={
            "job_id": f"job-A-{i}",
            "user_id": "user-A",
            "status": "COMPLETED",
            "budget_limit": Decimal("100"),
            "records_generated": 100,
            "created_at": (now - timedelta(days=5 - i)).isoformat(),
        })

    # Insert job for user B
    jobs_table.put_item(Item={
        "job_id": "job-B-0",
        "user_id": "user-B",
        "status": "COMPLETED",
        "budget_limit": Decimal("100"),
        "records_generated": 50,
        "created_at": (now - timedelta(days=3)).isoformat(),
    })

    # Insert cost records
    for i in range(3):
        cost_table.put_item(Item={
            "job_id": f"job-A-{i}",
            "timestamp": (now - timedelta(days=4 - i)).isoformat(),
            "estimated_cost": {
                "bedrock": Decimal("5.0"),
                "fargate": Decimal("1.0"),
                "s3": Decimal("0.2"),
                "total": Decimal("6.2"),
            },
            "model_id": "meta.llama3-1-8b-instruct-v1:0",
            "bedrock_tokens": 10000,
            "fargate_hours": Decimal("0.1"),
            "s3_operations": 50,
        })

    # User B cost record
    cost_table.put_item(Item={
        "job_id": "job-B-0",
        "timestamp": (now - timedelta(days=2)).isoformat(),
        "estimated_cost": {
            "bedrock": Decimal("20.0"),
            "fargate": Decimal("5.0"),
            "s3": Decimal("1.0"),
            "total": Decimal("26.0"),
        },
        "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "bedrock_tokens": 50000,
        "fargate_hours": Decimal("0.5"),
        "s3_operations": 100,
    })

    # Invoke as user A
    _mod.jobs_table = jobs_table
    _mod.cost_tracking_table = cost_table

    result = lambda_handler(_make_event(user_id="user-A"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # Only user A's 3 jobs
    assert body["summary"]["job_count"] == 3
    # Total: 3 * 6.2 = 18.6
    assert abs(body["summary"]["total_spend"] - 18.6) < 0.01
    # Time series should have entries
    assert len(body["time_series"]) > 0
    # By model should only have llama (user A's model)
    assert len(body["by_model"]) == 1
    assert "llama" in body["by_model"][0]["model_id"].lower()


@mock_aws
def test_cost_analytics_daily_aggregation():
    """
    Insert cost records across 5 days. Verify daily sums.
    """
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    now = datetime.now(UTC)

    jobs_table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-id-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    cost_table = dynamodb.create_table(
        TableName="plot-palette-CostTracking-test",
        KeySchema=[
            {"AttributeName": "job_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "COMPLETED",
        "budget_limit": Decimal("100"),
        "records_generated": 500,
        "created_at": (now - timedelta(days=10)).isoformat(),
    })

    # Two cost records on different days
    for day_offset in [8, 6]:
        cost_table.put_item(Item={
            "job_id": "job-1",
            "timestamp": (now - timedelta(days=day_offset)).isoformat(),
            "estimated_cost": {
                "bedrock": Decimal("10.0"),
                "fargate": Decimal("2.0"),
                "s3": Decimal("0.5"),
                "total": Decimal("12.5"),
            },
            "model_id": "meta.llama3-1-8b-instruct-v1:0",
            "bedrock_tokens": 20000,
            "fargate_hours": Decimal("0.2"),
            "s3_operations": 100,
        })

    _mod.jobs_table = jobs_table
    _mod.cost_tracking_table = cost_table

    result = lambda_handler(_make_event(user_id="user-A", period="30d"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # 2 daily entries
    assert len(body["time_series"]) == 2
    # Total: 2 * 12.5 = 25.0
    assert abs(body["summary"]["total_spend"] - 25.0) < 0.01
    assert body["summary"]["avg_cost_per_job"] == 25.0  # 1 job


@mock_aws
def test_cost_analytics_summary_stats():
    """Verify budget efficiency and average cost calculations."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    now = datetime.now(UTC)

    jobs_table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-id-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    cost_table = dynamodb.create_table(
        TableName="plot-palette-CostTracking-test",
        KeySchema=[
            {"AttributeName": "job_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Job with $50 budget, $10 cost
    jobs_table.put_item(Item={
        "job_id": "job-1",
        "user_id": "user-A",
        "status": "COMPLETED",
        "budget_limit": Decimal("50"),
        "records_generated": 200,
        "created_at": (now - timedelta(days=5)).isoformat(),
    })

    cost_table.put_item(Item={
        "job_id": "job-1",
        "timestamp": (now - timedelta(days=4)).isoformat(),
        "estimated_cost": {
            "bedrock": Decimal("7.0"),
            "fargate": Decimal("2.0"),
            "s3": Decimal("1.0"),
            "total": Decimal("10.0"),
        },
        "model_id": "meta.llama3-1-8b-instruct-v1:0",
        "bedrock_tokens": 20000,
        "fargate_hours": Decimal("0.2"),
        "s3_operations": 100,
    })

    _mod.jobs_table = jobs_table
    _mod.cost_tracking_table = cost_table

    result = lambda_handler(_make_event(user_id="user-A"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    assert body["summary"]["total_spend"] == 10.0
    assert body["summary"]["job_count"] == 1
    assert body["summary"]["avg_cost_per_job"] == 10.0
    # avg_cost_per_record: 10 / 200 = 0.05
    assert abs(body["summary"]["avg_cost_per_record"] - 0.05) < 0.001
    # Budget efficiency: 10/50 = 0.2
    assert abs(body["summary"]["budget_efficiency"] - 0.2) < 0.01
