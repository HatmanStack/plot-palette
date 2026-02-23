"""
Integration tests for batch job creation — calls actual lambda_handler against moto.

Uses moto's @mock_aws to create real DynamoDB tables, then invokes the
actual create_batch, get_batch, and list_batches lambda_handlers.
"""

import json
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

# Load handler modules
_create_mod = load_handler("lambdas/jobs/create_batch.py")
create_batch_handler = _create_mod.lambda_handler

_get_mod = load_handler("lambdas/jobs/get_batch.py")
get_batch_handler = _get_mod.lambda_handler

_list_mod = load_handler("lambdas/jobs/list_batches.py")
list_batches_handler = _list_mod.lambda_handler


def _create_jobs_table(dynamodb):
    """Create Jobs table."""
    return dynamodb.create_table(
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


def _create_batches_table(dynamodb):
    """Create Batches table."""
    return dynamodb.create_table(
        TableName="plot-palette-Batches-test",
        KeySchema=[{"AttributeName": "batch_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "batch_id", "AttributeType": "S"},
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


def _create_templates_table(dynamodb):
    """Create Templates table."""
    return dynamodb.create_table(
        TableName="plot-palette-Templates-test",
        KeySchema=[
            {"AttributeName": "template_id", "KeyType": "HASH"},
            {"AttributeName": "version", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "template_id", "AttributeType": "S"},
            {"AttributeName": "version", "AttributeType": "N"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _insert_template(templates_table, template_id="tmpl-123", version=1):
    """Insert a test template."""
    templates_table.put_item(
        Item={
            "template_id": template_id,
            "version": version,
            "name": "Test Template",
            "user_id": "user-A",
            "steps": [
                {
                    "id": "question",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "Generate a question about {{ author.name }}.",
                }
            ],
            "schema_requirements": ["author.name", "author.biography"],
            "created_at": "2025-01-01T00:00:00+00:00",
        }
    )


def _make_event(user_id, body):
    """Build API Gateway v2 event for batch creation."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "POST", "path": "/jobs/batch"},
            "requestId": "test-req-123",
        },
        "body": json.dumps(body),
    }


def _make_get_event(user_id, batch_id):
    """Build API Gateway v2 event for get_batch."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "GET", "path": f"/jobs/batches/{batch_id}"},
            "requestId": "test-req-456",
        },
        "pathParameters": {"batch_id": batch_id},
    }


def _make_list_event(user_id):
    """Build API Gateway v2 event for list_batches."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "GET", "path": "/jobs/batches"},
            "requestId": "test-req-789",
        },
        "queryStringParameters": None,
    }


@mock_aws
def test_batch_create_stores_jobs_and_batch():
    """Create batch with 3 model_tier sweep values. Assert 3 jobs in Jobs table
    and batch record in Batches table with 3 job_ids."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)
    batches_table = _create_batches_table(dynamodb)
    templates_table = _create_templates_table(dynamodb)
    _insert_template(templates_table)

    # Wire tables into handler module
    _create_mod.jobs_table = jobs_table
    _create_mod.batches_table = batches_table
    _create_mod.templates_table = templates_table

    # Mock SFN client
    mock_sfn = MagicMock()
    mock_sfn.start_execution.return_value = {
        "executionArn": "arn:aws:states:us-east-1:123456789012:execution:test:job-123",
    }
    _create_mod.sfn_client = mock_sfn

    event = _make_event(
        "user-A",
        {
            "name": "Model comparison test",
            "template_id": "tmpl-123",
            "template_version": 1,
            "seed_data_path": "seed-data/user-A/test.jsonl",
            "base_config": {
                "budget_limit": 10.0,
                "num_records": 100,
                "output_format": "JSONL",
            },
            "sweep": {"model_tier": ["tier-1", "tier-2", "tier-3"]},
        },
    )

    result = create_batch_handler(event, None)
    assert result["statusCode"] == 201

    body = json.loads(result["body"])
    assert body["job_count"] == 3
    assert len(body["job_ids"]) == 3

    # Verify 3 jobs in DynamoDB
    for job_id in body["job_ids"]:
        job_resp = jobs_table.get_item(Key={"job_id": job_id})
        assert "Item" in job_resp
        assert job_resp["Item"]["user_id"] == "user-A"

    # Verify batch record
    batch_resp = batches_table.get_item(Key={"batch_id": body["batch_id"]})
    assert "Item" in batch_resp
    batch = batch_resp["Item"]
    assert batch["name"] == "Model comparison test"
    assert batch["total_jobs"] == 3
    assert len(batch["job_ids"]) == 3
    assert batch["sweep_config"] == {"model_tier": ["tier-1", "tier-2", "tier-3"]}

    # Verify SFN was called 3 times
    assert mock_sfn.start_execution.call_count == 3


@mock_aws
def test_get_batch_returns_batch_with_jobs():
    """Create batch then fetch it. Assert response includes job details."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    jobs_table = _create_jobs_table(dynamodb)
    batches_table = _create_batches_table(dynamodb)
    templates_table = _create_templates_table(dynamodb)
    _insert_template(templates_table)

    # Create batch first
    _create_mod.jobs_table = jobs_table
    _create_mod.batches_table = batches_table
    _create_mod.templates_table = templates_table

    mock_sfn = MagicMock()
    mock_sfn.start_execution.return_value = {
        "executionArn": "arn:aws:states:us-east-1:123456789012:execution:test:job-123",
    }
    _create_mod.sfn_client = mock_sfn

    create_event = _make_event(
        "user-A",
        {
            "name": "Fetch test batch",
            "template_id": "tmpl-123",
            "template_version": 1,
            "seed_data_path": "seed-data/user-A/test.jsonl",
            "base_config": {
                "budget_limit": 5.0,
                "num_records": 50,
                "output_format": "JSONL",
            },
            "sweep": {"model_tier": ["tier-1", "tier-2"]},
        },
    )

    create_result = create_batch_handler(create_event, None)
    assert create_result["statusCode"] == 201
    batch_id = json.loads(create_result["body"])["batch_id"]

    # Wire get_batch handler — set JOBS_TABLE_NAME so batch_get_item finds the table
    _get_mod.batches_table = batches_table
    _get_mod.jobs_table = jobs_table
    _get_mod.dynamodb = dynamodb

    with patch.dict(os.environ, {"JOBS_TABLE_NAME": "plot-palette-Jobs-test"}):
        get_event = _make_get_event("user-A", batch_id)
        get_result = get_batch_handler(get_event, None)

    assert get_result["statusCode"] == 200
    body = json.loads(get_result["body"])
    assert body["batch_id"] == batch_id
    assert body["name"] == "Fetch test batch"
    assert int(body["total_jobs"]) == 2
    assert len(body["jobs"]) == 2


@mock_aws
def test_get_batch_rejects_non_owner():
    """User B tries to access User A's batch. Assert 403."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    batches_table = _create_batches_table(dynamodb)

    # Insert batch directly
    batches_table.put_item(
        Item={
            "batch_id": "batch-owned-by-A",
            "user_id": "user-A",
            "name": "A's batch",
            "status": "RUNNING",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
            "job_ids": [],
            "total_jobs": 1,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "template_id": "tmpl-123",
            "template_version": 1,
            "sweep_config": {},
            "total_cost": Decimal("0"),
        }
    )

    _get_mod.batches_table = batches_table

    get_event = _make_get_event("user-B", "batch-owned-by-A")
    result = get_batch_handler(get_event, None)

    assert result["statusCode"] == 403


@mock_aws
def test_list_batches_user_scoped():
    """User A has 2 batches, user B has 1. Assert user A sees only 2."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    batches_table = _create_batches_table(dynamodb)

    # Insert batches for two users
    for i, (uid, name) in enumerate([
        ("user-A", "Batch A1"),
        ("user-A", "Batch A2"),
        ("user-B", "Batch B1"),
    ]):
        batches_table.put_item(
            Item={
                "batch_id": f"batch-{i}",
                "user_id": uid,
                "name": name,
                "status": "COMPLETED",
                "created_at": f"2025-01-0{i + 1}T00:00:00+00:00",
                "updated_at": f"2025-01-0{i + 1}T00:00:00+00:00",
                "job_ids": [],
                "total_jobs": 1,
                "completed_jobs": 1,
                "failed_jobs": 0,
                "template_id": "tmpl-123",
                "template_version": 1,
                "sweep_config": {},
                "total_cost": Decimal("0"),
            }
        )

    _list_mod.batches_table = batches_table

    list_event = _make_list_event("user-A")
    result = list_batches_handler(list_event, None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["batches"]) == 2
    names = {b["name"] for b in body["batches"]}
    assert names == {"Batch A1", "Batch A2"}
