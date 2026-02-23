"""
Integration tests for partial export — calls actual lambda_handler against moto.

Uses moto's @mock_aws to create real DynamoDB tables and S3 buckets,
then invokes the actual download_partial.lambda_handler.
"""

import json
import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/jobs/download_partial.py")
lambda_handler = _mod.lambda_handler


def _make_event(user_id="user-123", job_id="job-integ-001"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"job_id": job_id},
        "queryStringParameters": None,
    }


@mock_aws
def test_partial_export_concatenates_batch_files():
    """
    Full integration test: create DynamoDB job, upload batch files to S3,
    invoke actual lambda_handler, verify response includes download_url.
    """
    # Set up DynamoDB
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    table.put_item(
        Item={
            "job_id": "job-integ-001",
            "user_id": "user-123",
            "status": "RUNNING",
            "records_generated": 150,
            "config": {"output_format": "JSONL"},
        }
    )

    # Set up S3 with batch files
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="plot-palette-data-test")

    batch_data = {
        "jobs/job-integ-001/outputs/batch-0000.jsonl": b'{"id": 1, "text": "record one"}\n{"id": 2, "text": "record two"}\n',
        "jobs/job-integ-001/outputs/batch-0001.jsonl": b'{"id": 3, "text": "record three"}\n',
        "jobs/job-integ-001/outputs/batch-0002.jsonl": b'{"id": 4, "text": "record four"}\n{"id": 5, "text": "record five"}\n',
    }

    for key, data in batch_data.items():
        s3.put_object(Bucket="plot-palette-data-test", Key=key, Body=data)

    # Invoke actual handler with moto-backed clients
    _mod.jobs_table = table
    _mod.s3_client = s3
    _mod.bucket_name = "plot-palette-data-test"

    result = lambda_handler(_make_event(), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "download_url" in body
    assert body["records_available"] == 150
    assert body["format"] == "jsonl"
    assert "partial" in body["filename"]

    # Verify the concatenated file was created in S3
    exports = s3.list_objects_v2(
        Bucket="plot-palette-data-test",
        Prefix="jobs/job-integ-001/exports/partial-",
    )
    assert exports["KeyCount"] == 1

    # Verify contents are concatenated correctly
    partial_key = exports["Contents"][0]["Key"]
    obj = s3.get_object(Bucket="plot-palette-data-test", Key=partial_key)
    content = obj["Body"].read().decode("utf-8")
    lines = [line for line in content.strip().split("\n") if line]
    assert len(lines) == 5

    for line in lines:
        parsed = json.loads(line)
        assert "id" in parsed
        assert "text" in parsed


@mock_aws
def test_partial_export_no_batch_files():
    """Integration test: job exists with records but no S3 batch files -> 404."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    table.put_item(
        Item={
            "job_id": "job-integ-002",
            "user_id": "user-123",
            "status": "RUNNING",
            "records_generated": 50,
        }
    )

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="plot-palette-data-test")

    _mod.jobs_table = table
    _mod.s3_client = s3
    _mod.bucket_name = "plot-palette-data-test"

    result = lambda_handler(_make_event(job_id="job-integ-002"), None)

    assert result["statusCode"] == 404
    body = json.loads(result["body"])
    assert "no batch files" in body["error"].lower()


@mock_aws
def test_partial_export_ownership_check():
    """Integration test: verify ownership returns 403 for non-owner."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    table.put_item(
        Item={
            "job_id": "job-integ-003",
            "user_id": "other-user",
            "status": "RUNNING",
            "records_generated": 100,
        }
    )

    _mod.jobs_table = table
    _mod.s3_client = boto3.client("s3", region_name="us-east-1")
    _mod.bucket_name = "plot-palette-data-test"

    result = lambda_handler(
        _make_event(user_id="user-123", job_id="job-integ-003"), None
    )

    assert result["statusCode"] == 403
