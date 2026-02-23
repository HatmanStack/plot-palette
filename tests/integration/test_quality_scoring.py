"""
Integration tests for quality scoring pipeline.

Uses moto's @mock_aws to create real DynamoDB tables and S3 buckets,
then invokes the actual Lambda handlers.
"""

import json
import os
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from tests.unit.handler_import import load_handler

# Load handler modules
_score_mod = load_handler("lambdas/quality/score_job.py")
score_job_handler = _score_mod.lambda_handler

_get_mod = load_handler("lambdas/quality/get_quality.py")
get_quality_handler = _get_mod.lambda_handler

_trigger_mod = load_handler("lambdas/quality/trigger_scoring.py")
trigger_scoring_handler = _trigger_mod.lambda_handler


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


def _create_quality_table(dynamodb):
    """Create QualityMetrics table."""
    return dynamodb.create_table(
        TableName="plot-palette-QualityMetrics-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _make_scoring_response(scores):
    """Build a mock Bedrock response."""
    body = MagicMock()
    body.read.return_value = json.dumps(
        {
            "content": [
                {"type": "text", "text": json.dumps(scores)}
            ]
        }
    ).encode("utf-8")
    return {"body": body}


def _make_event(method, path, path_params=None, body=None, user_id="user-123"):
    """Build an API Gateway v2 event."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": method, "path": path},
            "requestId": "req-integ-001",
        },
        "pathParameters": path_params or {},
        "queryStringParameters": None,
        "body": json.dumps(body) if body else None,
    }


@mock_aws
class TestQualityScoringPipeline:
    """End-to-end scoring integration test."""

    def test_full_scoring_pipeline(self):
        """Create tables/bucket, insert job, upload JSONL, run scoring, verify results."""
        # Setup AWS resources
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        s3 = boto3.client("s3", region_name="us-east-1")

        jobs_table = _create_jobs_table(dynamodb)
        templates_table = _create_templates_table(dynamodb)
        quality_table = _create_quality_table(dynamodb)
        s3.create_bucket(Bucket="test-bucket")

        # Insert completed job
        jobs_table.put_item(
            Item={
                "job_id": "job-integ-1",
                "user_id": "user-123",
                "status": "COMPLETED",
                "config": {
                    "template_id": "tmpl-integ-1",
                    "template_version": 1,
                    "output_format": "JSONL",
                },
                "records_generated": 50,
                "budget_limit": Decimal("10"),
                "cost_estimate": Decimal("5"),
                "created_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T11:00:00",
            }
        )

        # Insert template
        templates_table.put_item(
            Item={
                "template_id": "tmpl-integ-1",
                "version": 1,
                "name": "Integration Test Template",
                "user_id": "user-123",
                "schema_requirements": ["author.name", "poem.text"],
                "steps": json.dumps([
                    {"id": "gen", "model_tier": "tier-1", "prompt": "Generate..."}
                ]),
                "is_public": False,
                "created_at": "2025-12-01T09:00:00",
            }
        )

        # Upload JSONL export with 50 records
        records = [
            {
                "seed_data_id": f"seed-{i}",
                "generation_result": f"Generated unique content for record {i} about topic {i}",
            }
            for i in range(50)
        ]
        jsonl = "\n".join(json.dumps(r) for r in records)
        s3.put_object(
            Bucket="test-bucket",
            Key="jobs/job-integ-1/exports/dataset.jsonl",
            Body=jsonl.encode("utf-8"),
        )

        # Wire up handler module to use real DynamoDB/S3
        _score_mod.jobs_table = jobs_table
        _score_mod.templates_table = templates_table
        _score_mod.quality_table = quality_table
        _score_mod.s3_client = s3
        _score_mod.bucket_name = "test-bucket"

        # Mock Bedrock (can't use real Bedrock in tests)
        mock_bedrock = MagicMock()
        default_score = {"coherence": 0.85, "relevance": 0.9, "format_compliance": 0.95, "detail": "Good"}
        mock_bedrock.invoke_model.side_effect = [
            _make_scoring_response([default_score] * 5) for _ in range(4)
        ]
        _score_mod.bedrock_client = mock_bedrock

        # Run scoring
        result = score_job_handler({"job_id": "job-integ-1"}, None)

        # Verify results stored in DynamoDB
        quality_response = quality_table.get_item(Key={"job_id": "job-integ-1"})
        assert "Item" in quality_response
        metrics = quality_response["Item"]

        assert metrics["status"] == "COMPLETED"
        assert metrics["sample_size"] == 20
        assert metrics["total_records"] == 50
        assert float(metrics["aggregate_scores"]["coherence"]) == pytest.approx(0.85, abs=0.01)
        assert float(metrics["aggregate_scores"]["relevance"]) == pytest.approx(0.9, abs=0.01)
        assert float(metrics["scoring_cost"]) > 0


@mock_aws
class TestQualityApiIntegration:
    """Integration tests for quality API endpoints."""

    def test_get_quality_after_scoring(self):
        """Insert quality metrics, invoke GET handler, verify response."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        jobs_table = _create_jobs_table(dynamodb)
        quality_table = _create_quality_table(dynamodb)

        # Insert job
        jobs_table.put_item(
            Item={
                "job_id": "job-api-1",
                "user_id": "user-123",
                "status": "COMPLETED",
            }
        )

        # Insert quality metrics directly
        quality_table.put_item(
            Item={
                "job_id": "job-api-1",
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
                "record_scores": [],
                "scoring_cost": Decimal("0.05"),
                "status": "COMPLETED",
                "ttl": 9999999999,
            }
        )

        # Wire up handler
        _get_mod.jobs_table = jobs_table
        _get_mod.quality_table = quality_table

        # Invoke GET
        event = _make_event("GET", "/jobs/job-api-1/quality", {"job_id": "job-api-1"})
        response = get_quality_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["job_id"] == "job-api-1"
        assert body["overall_score"] == 0.86
        assert body["status"] == "COMPLETED"

    def test_trigger_scoring_rejects_already_scored(self):
        """Invoke trigger on already-scored job, verify 409."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        jobs_table = _create_jobs_table(dynamodb)
        quality_table = _create_quality_table(dynamodb)

        # Insert completed job
        jobs_table.put_item(
            Item={
                "job_id": "job-api-2",
                "user_id": "user-123",
                "status": "COMPLETED",
            }
        )

        # Insert existing quality metrics (COMPLETED)
        quality_table.put_item(
            Item={
                "job_id": "job-api-2",
                "status": "COMPLETED",
                "scored_at": "2025-12-01T10:00:00",
                "sample_size": 20,
                "total_records": 100,
                "model_used_for_scoring": "test",
                "aggregate_scores": {},
                "diversity_score": Decimal("0.8"),
                "overall_score": Decimal("0.85"),
                "record_scores": [],
                "scoring_cost": Decimal("0.05"),
                "ttl": 9999999999,
            }
        )

        # Wire up handler
        _trigger_mod.jobs_table = jobs_table
        _trigger_mod.quality_table = quality_table
        _trigger_mod.lambda_client = MagicMock()

        # Invoke POST
        event = _make_event("POST", "/jobs/job-api-2/quality", {"job_id": "job-api-2"})
        response = trigger_scoring_handler(event, None)

        assert response["statusCode"] == 409
        # Lambda invoke should NOT have been called
        _trigger_mod.lambda_client.invoke.assert_not_called()
