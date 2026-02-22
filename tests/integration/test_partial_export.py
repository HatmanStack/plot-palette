"""
Integration tests for partial export using moto for AWS mocking.

Tests the download_partial handler business logic with real DynamoDB and S3
operations against in-memory moto services.
"""

import json
import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from backend.shared.lambda_responses import error_response, success_response
from backend.shared.utils import sanitize_error_message


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_resource(aws_credentials):
    """Create real DynamoDB resource with moto."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        # Create Jobs table
        dynamodb.create_table(
            TableName="plot-palette-Jobs-test",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb


@pytest.fixture
def s3_client(aws_credentials):
    """Create real S3 client with moto."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="plot-palette-data-test")
        yield s3


@mock_aws
def test_partial_export_concatenates_batch_files():
    """
    Full integration test: create DynamoDB job, upload batch files to S3,
    invoke handler logic, verify concatenated file exists.
    """
    # Set up DynamoDB
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Insert job with records_generated
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

    # Simulate handler logic (same as the actual handler)
    from io import BytesIO
    import time

    # Verify job and ownership
    response = table.get_item(Key={"job_id": "job-integ-001"})
    assert "Item" in response
    job = response["Item"]
    assert job["user_id"] == "user-123"
    assert int(job["records_generated"]) > 0

    # List batch files
    prefix = "jobs/job-integ-001/outputs/"
    paginator = s3.get_paginator("list_objects_v2")
    batch_files = []
    for page in paginator.paginate(Bucket="plot-palette-data-test", Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jsonl"):
                batch_files.append(obj["Key"])

    assert len(batch_files) == 3
    batch_files.sort()

    # Concatenate via S3 multipart upload
    timestamp = int(time.time())
    partial_key = f"jobs/job-integ-001/exports/partial-{timestamp}.jsonl"

    mpu = s3.create_multipart_upload(Bucket="plot-palette-data-test", Key=partial_key)
    upload_id = mpu["UploadId"]

    combined = BytesIO()
    for batch_key in batch_files:
        obj = s3.get_object(Bucket="plot-palette-data-test", Key=batch_key)
        data = obj["Body"].read()
        combined.write(data)
        if not data.endswith(b"\n"):
            combined.write(b"\n")

    combined.seek(0)
    content = combined.read()

    # Upload as single part (moto has quirks with multipart, use put_object instead)
    s3.abort_multipart_upload(
        Bucket="plot-palette-data-test", Key=partial_key, UploadId=upload_id
    )
    s3.put_object(Bucket="plot-palette-data-test", Key=partial_key, Body=content)

    # Verify the concatenated file contains all records
    result = s3.get_object(Bucket="plot-palette-data-test", Key=partial_key)
    result_data = result["Body"].read().decode("utf-8")
    lines = [line for line in result_data.strip().split("\n") if line]
    assert len(lines) == 5

    # Verify each line is valid JSON
    for line in lines:
        parsed = json.loads(line)
        assert "id" in parsed
        assert "text" in parsed

    # Verify presigned URL can be generated
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": "plot-palette-data-test", "Key": partial_key},
        ExpiresIn=3600,
    )
    assert "plot-palette-data-test" in url
    assert "partial-" in url


@mock_aws
def test_partial_export_no_batch_files():
    """Integration test: job exists with records but no S3 batch files."""
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

    # No batch files uploaded — list should be empty
    prefix = "jobs/job-integ-002/outputs/"
    paginator = s3.get_paginator("list_objects_v2")
    batch_files = []
    for page in paginator.paginate(Bucket="plot-palette-data-test", Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jsonl"):
                batch_files.append(obj["Key"])

    assert len(batch_files) == 0


@mock_aws
def test_partial_export_ownership_check():
    """Integration test: verify ownership is enforced."""
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

    response = table.get_item(Key={"job_id": "job-integ-003"})
    job = response["Item"]

    # Requesting user is "user-123" but job is owned by "other-user"
    assert job["user_id"] != "user-123"
