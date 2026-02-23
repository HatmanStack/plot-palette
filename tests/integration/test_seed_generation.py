"""
Integration tests for seed data generation — calls actual lambda_handler against moto.

Uses moto's @mock_aws to create real DynamoDB + S3, then invokes the
actual generate_seed_data.lambda_handler with a mocked Bedrock client.
"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/seed_data/generate_seed_data.py")
lambda_handler = _mod.lambda_handler


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


def _create_s3_bucket(s3_client, bucket_name="plot-palette-data-test"):
    """Create S3 bucket."""
    s3_client.create_bucket(Bucket=bucket_name)


def _insert_template(templates_table, template_id="tmpl-seed", version=1):
    """Insert a template with schema_requirements."""
    templates_table.put_item(
        Item={
            "template_id": template_id,
            "version": version,
            "name": "Seed Test Template",
            "user_id": "user-A",
            "steps": [
                {
                    "id": "question",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "Write about {{ author.name }}: {{ author.biography }}",
                }
            ],
            "schema_requirements": ["author.name", "author.biography"],
            "created_at": "2025-01-01T00:00:00+00:00",
        }
    )


def _make_bedrock_response(records_json):
    """Build a mock Bedrock response body for Llama-style output."""
    return {
        "body": MagicMock(
            read=lambda: json.dumps({"generation": records_json}).encode()
        )
    }


def _make_event(user_id, body):
    """Build API Gateway v2 event."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "POST", "path": "/seed-data/generate"},
            "requestId": "test-req-seed-1",
        },
        "body": json.dumps(body),
    }


@mock_aws
def test_generate_uploads_valid_records_to_s3():
    """Generate 3 records, all valid. Assert JSONL uploaded to S3 with correct structure."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
    templates_table = _create_templates_table(dynamodb)
    _insert_template(templates_table)
    _create_s3_bucket(s3)

    # Wire handler
    _mod.templates_table = templates_table
    _mod.s3_client = s3

    # Mock Bedrock to return valid JSON array
    valid_records = [
        {"author": {"name": "Emily Dickinson", "biography": "American poet"}},
        {"author": {"name": "Walt Whitman", "biography": "Leaves of Grass poet"}},
        {"author": {"name": "Maya Angelou", "biography": "I Know Why the Caged Bird Sings"}},
    ]
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = _make_bedrock_response(
        json.dumps(valid_records)
    )
    _mod.bedrock_client = mock_bedrock

    event = _make_event(
        "user-A",
        {
            "template_id": "tmpl-seed",
            "count": 3,
            "model_tier": "tier-1",
        },
    )

    with patch.dict(os.environ, {"BUCKET_NAME": "plot-palette-data-test"}):
        result = lambda_handler(event, None)

    assert result["statusCode"] == 200

    body = json.loads(result["body"])
    assert body["records_generated"] == 3
    assert body["records_invalid"] == 0
    assert body["s3_key"].startswith("seed-data/user-A/generated-")

    # Verify file in S3
    s3_obj = s3.get_object(Bucket="plot-palette-data-test", Key=body["s3_key"])
    content = s3_obj["Body"].read().decode("utf-8")
    lines = content.strip().split("\n")
    assert len(lines) == 3

    # Each line is valid JSON with correct structure
    for line in lines:
        record = json.loads(line)
        assert "author" in record
        assert "name" in record["author"]
        assert "biography" in record["author"]


@mock_aws
def test_generate_filters_invalid_records():
    """Generate 5 records, 2 missing required fields. Assert only 3 uploaded."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
    templates_table = _create_templates_table(dynamodb)
    _insert_template(templates_table)
    _create_s3_bucket(s3)

    _mod.templates_table = templates_table
    _mod.s3_client = s3

    records = [
        {"author": {"name": "Valid 1", "biography": "Bio 1"}},
        {"author": {"name": "Valid 2", "biography": "Bio 2"}},
        {"author": {"name": "Valid 3", "biography": "Bio 3"}},
        {"author": {"name": "Missing bio"}},  # missing biography
        {"wrong_key": "no author at all"},  # completely wrong structure
    ]
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = _make_bedrock_response(
        json.dumps(records)
    )
    _mod.bedrock_client = mock_bedrock

    event = _make_event(
        "user-A",
        {"template_id": "tmpl-seed", "count": 5, "model_tier": "tier-1"},
    )

    with patch.dict(os.environ, {"BUCKET_NAME": "plot-palette-data-test"}):
        result = lambda_handler(event, None)

    assert result["statusCode"] == 200

    body = json.loads(result["body"])
    assert body["records_generated"] == 3
    assert body["records_invalid"] == 2

    # Verify S3 only has 3 lines
    s3_obj = s3.get_object(Bucket="plot-palette-data-test", Key=body["s3_key"])
    content = s3_obj["Body"].read().decode("utf-8")
    lines = content.strip().split("\n")
    assert len(lines) == 3


@mock_aws
def test_generate_handles_markdown_wrapped_json():
    """Bedrock returns JSON wrapped in markdown code blocks. Assert parses correctly."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
    templates_table = _create_templates_table(dynamodb)
    _insert_template(templates_table)
    _create_s3_bucket(s3)

    _mod.templates_table = templates_table
    _mod.s3_client = s3

    records = [{"author": {"name": "Rumi", "biography": "Persian poet"}}]
    markdown_json = f"```json\n{json.dumps(records)}\n```"

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = _make_bedrock_response(markdown_json)
    _mod.bedrock_client = mock_bedrock

    event = _make_event(
        "user-A",
        {"template_id": "tmpl-seed", "count": 1, "model_tier": "tier-1"},
    )

    with patch.dict(os.environ, {"BUCKET_NAME": "plot-palette-data-test"}):
        result = lambda_handler(event, None)

    assert result["statusCode"] == 200

    body = json.loads(result["body"])
    assert body["records_generated"] == 1


@mock_aws
def test_generate_template_not_found():
    """Request with non-existent template. Assert 404."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    templates_table = _create_templates_table(dynamodb)

    _mod.templates_table = templates_table

    event = _make_event(
        "user-A",
        {"template_id": "nonexistent-template", "count": 5},
    )

    result = lambda_handler(event, None)
    assert result["statusCode"] == 404


@mock_aws
def test_generate_includes_example_data_in_prompt():
    """When example_data is provided, assert Bedrock receives prompt with example."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
    templates_table = _create_templates_table(dynamodb)
    _insert_template(templates_table)
    _create_s3_bucket(s3)

    _mod.templates_table = templates_table
    _mod.s3_client = s3

    records = [{"author": {"name": "Test", "biography": "Test bio"}}]
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = _make_bedrock_response(
        json.dumps(records)
    )
    _mod.bedrock_client = mock_bedrock

    event = _make_event(
        "user-A",
        {
            "template_id": "tmpl-seed",
            "count": 1,
            "model_tier": "tier-1",
            "example_data": {"author": {"name": "Example", "biography": "Example bio"}},
            "instructions": "Generate diverse authors",
        },
    )

    with patch.dict(os.environ, {"BUCKET_NAME": "plot-palette-data-test"}):
        result = lambda_handler(event, None)

    assert result["statusCode"] == 200

    # Verify the prompt sent to Bedrock includes example data and instructions
    call_args = mock_bedrock.invoke_model.call_args
    request_body = json.loads(call_args.kwargs["body"])
    prompt_text = request_body["prompt"]
    assert "Example" in prompt_text
    assert "Generate diverse authors" in prompt_text
