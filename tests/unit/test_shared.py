"""
Unit tests for backend shared library.

Tests models, constants, and utility functions.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import json

from backend.shared.models import (
    JobConfig,
    TemplateDefinition,
    TemplateStep,
    CheckpointState,
    CostBreakdown,
    QueueItem,
)
from backend.shared.constants import (
    JobStatus,
    ExportFormat,
    MODEL_PRICING,
    MODEL_TIERS,
    FARGATE_SPOT_PRICING,
    CHECKPOINT_INTERVAL,
)
from backend.shared.utils import (
    generate_job_id,
    generate_template_id,
    calculate_bedrock_cost,
    calculate_fargate_cost,
    calculate_s3_cost,
    get_nested_field,
    set_nested_field,
    parse_etag,
    resolve_model_id,
    validate_seed_data,
    format_cost,
    format_timestamp,
    parse_timestamp,
)


class TestJobConfig:
    """Test JobConfig model."""

    def test_job_config_creation(self):
        """Test creating a JobConfig instance."""
        job = JobConfig(
            job_id="test-job-123",
            user_id="user-456",
            status=JobStatus.QUEUED,
            created_at=datetime(2025, 11, 19, 10, 0, 0),
            updated_at=datetime(2025, 11, 19, 10, 0, 0),
            config={"template_id": "template-1", "seed_data_path": "s3://bucket/seed.json"},
            budget_limit=100.0,
        )

        assert job.job_id == "test-job-123"
        assert job.user_id == "user-456"
        assert job.status == JobStatus.QUEUED
        assert job.budget_limit == 100.0
        assert job.tokens_used == 0
        assert job.records_generated == 0
        assert job.cost_estimate == 0.0

    def test_job_config_to_dynamodb(self):
        """Test JobConfig serialization to DynamoDB format."""
        job = JobConfig(
            job_id="test-job-123",
            user_id="user-456",
            status=JobStatus.RUNNING,
            created_at=datetime(2025, 11, 19, 10, 0, 0),
            updated_at=datetime(2025, 11, 19, 10, 30, 0),
            config={"key": "value"},
            budget_limit=50.0,
            tokens_used=10000,
            records_generated=100,
            cost_estimate=5.25,
        )

        dynamodb_item = job.to_dynamodb()

        assert dynamodb_item["job_id"]["S"] == "test-job-123"
        assert dynamodb_item["user_id"]["S"] == "user-456"
        assert dynamodb_item["status"]["S"] == "RUNNING"
        assert dynamodb_item["budget_limit"]["N"] == "50.0"
        assert dynamodb_item["tokens_used"]["N"] == "10000"
        assert dynamodb_item["records_generated"]["N"] == "100"
        assert dynamodb_item["cost_estimate"]["N"] == "5.25"


class TestTemplateDefinition:
    """Test TemplateDefinition model."""

    def test_template_creation(self):
        """Test creating a template with steps."""
        step = TemplateStep(
            id="question",
            model="meta.llama3-1-8b-instruct-v1:0",
            prompt="Generate a question about {{ author.name }}",
        )

        template = TemplateDefinition(
            template_id="template-123",
            version=1,
            name="Creative Writing Template",
            user_id="user-456",
            schema_requirements=["author.name", "author.biography"],
            steps=[step],
            is_public=False,
        )

        assert template.template_id == "template-123"
        assert template.version == 1
        assert len(template.steps) == 1
        assert template.steps[0].id == "question"
        assert len(template.schema_requirements) == 2

    def test_template_step_validation(self):
        """Test template step model tier validation."""
        # Valid tier
        step = TemplateStep(id="step1", model_tier="tier-1", prompt="Test prompt")
        assert step.model_tier == "tier-1"

        # Invalid tier should raise validation error
        with pytest.raises(ValueError):
            TemplateStep(id="step2", model_tier="invalid-tier", prompt="Test prompt")


class TestCheckpointState:
    """Test CheckpointState model."""

    def test_checkpoint_creation(self):
        """Test creating a checkpoint state."""
        checkpoint = CheckpointState(
            job_id="job-123",
            records_generated=1250,
            current_batch=25,
            tokens_used=450000,
            cost_accumulated=12.50,
            resume_state={"seed_data_index": 42, "template_step": "answer_generation"},
        )

        assert checkpoint.job_id == "job-123"
        assert checkpoint.records_generated == 1250
        assert checkpoint.tokens_used == 450000
        assert checkpoint.cost_accumulated == 12.50

    def test_checkpoint_serialization(self):
        """Test checkpoint JSON serialization."""
        checkpoint = CheckpointState(
            job_id="job-123",
            records_generated=100,
            current_batch=2,
            tokens_used=5000,
            cost_accumulated=1.25,
        )

        json_str = checkpoint.to_json()
        assert "job-123" in json_str
        assert "100" in json_str

        # Test deserialization
        restored = CheckpointState.from_json(json_str, etag="abc123")
        assert restored.job_id == checkpoint.job_id
        assert restored.records_generated == checkpoint.records_generated
        assert restored.etag == "abc123"


class TestCostBreakdown:
    """Test CostBreakdown model."""

    def test_cost_breakdown_to_dynamodb(self):
        """Test cost breakdown DynamoDB serialization."""
        cost = CostBreakdown(
            job_id="job-123",
            timestamp=datetime(2025, 11, 19, 10, 0, 0),
            bedrock_tokens=100000,
            fargate_hours=0.5,
            s3_operations=50,
            estimated_cost=3.50,
            model_id="meta.llama3-1-8b-instruct-v1:0",
        )

        dynamodb_item = cost.to_dynamodb()

        assert dynamodb_item["job_id"]["S"] == "job-123"
        assert dynamodb_item["bedrock_tokens"]["N"] == "100000"
        assert dynamodb_item["fargate_hours"]["N"] == "0.5"
        assert dynamodb_item["estimated_cost"]["N"] == "3.5"
        assert "ttl" in dynamodb_item


class TestQueueItem:
    """Test QueueItem model."""

    def test_queue_item_composite_key(self):
        """Test queue item composite sort key generation."""
        timestamp = datetime(2025, 11, 19, 10, 0, 0)
        item = QueueItem(
            status=JobStatus.QUEUED,
            job_id="job-123",
            timestamp=timestamp,
            priority=0,
        )

        expected_key = f"job-123#{timestamp.isoformat()}"
        assert item.job_id_timestamp == expected_key


class TestUtilityFunctions:
    """Test utility functions."""

    def test_generate_job_id(self):
        """Test UUID job ID generation."""
        job_id = generate_job_id()
        assert len(job_id) == 36  # UUID4 format with dashes
        assert job_id.count("-") == 4

    def test_generate_template_id(self):
        """Test UUID template ID generation."""
        template_id = generate_template_id()
        assert len(template_id) == 36
        assert template_id.count("-") == 4

    def test_calculate_bedrock_cost(self):
        """Test Bedrock cost calculation."""
        # Test input tokens for Claude Sonnet
        cost = calculate_bedrock_cost(
            tokens=1_000_000,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            is_input=True,
        )
        assert cost == 3.00

        # Test output tokens for Claude Sonnet
        cost = calculate_bedrock_cost(
            tokens=1_000_000,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            is_input=False,
        )
        assert cost == 15.00

        # Test Llama 3.1 8B
        cost = calculate_bedrock_cost(
            tokens=1_000_000, model_id="meta.llama3-1-8b-instruct-v1:0", is_input=True
        )
        assert cost == 0.30

    def test_calculate_bedrock_cost_unknown_model(self):
        """Test error handling for unknown model."""
        with pytest.raises(ValueError, match="Unknown model ID"):
            calculate_bedrock_cost(tokens=1000, model_id="unknown-model", is_input=True)

    def test_calculate_fargate_cost(self):
        """Test Fargate Spot cost calculation."""
        # 0.5 vCPU, 1 GB memory, 2 hours
        cost = calculate_fargate_cost(vcpu=0.5, memory_gb=1.0, hours=2.0)

        expected_vcpu_cost = 0.5 * FARGATE_SPOT_PRICING["vcpu"] * 2.0
        expected_memory_cost = 1.0 * FARGATE_SPOT_PRICING["memory"] * 2.0
        expected_total = expected_vcpu_cost + expected_memory_cost

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_calculate_s3_cost(self):
        """Test S3 API operation cost calculation."""
        cost = calculate_s3_cost(puts=1000, gets=5000)

        expected_put_cost = 1000 * (0.005 / 1000)
        expected_get_cost = 5000 * (0.0004 / 1000)
        expected_total = expected_put_cost + expected_get_cost

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_get_nested_field(self):
        """Test retrieving nested dictionary values."""
        data = {"author": {"name": "Jane Doe", "biography": "Born in 1980..."}}

        assert get_nested_field(data, "author.name") == "Jane Doe"
        assert get_nested_field(data, "author.biography") == "Born in 1980..."
        assert get_nested_field(data, "author.missing") is None
        assert get_nested_field(data, "missing.field") is None

    def test_set_nested_field(self):
        """Test setting nested dictionary values."""
        data = {}
        set_nested_field(data, "author.name", "Jane Doe")
        set_nested_field(data, "author.biography", "Test bio")

        assert data["author"]["name"] == "Jane Doe"
        assert data["author"]["biography"] == "Test bio"

    def test_parse_etag(self):
        """Test ETag parsing (quote removal)."""
        assert parse_etag('"abc123"') == "abc123"
        assert parse_etag("abc123") == "abc123"
        assert parse_etag('"def456"') == "def456"

    def test_resolve_model_id(self):
        """Test model tier resolution."""
        # Test tier aliases
        assert resolve_model_id("tier-1") == MODEL_TIERS["tier-1"]
        assert resolve_model_id("cheap") == MODEL_TIERS["cheap"]
        assert resolve_model_id("premium") == MODEL_TIERS["premium"]

        # Test direct model ID pass-through
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert resolve_model_id(model_id) == model_id

    def test_validate_seed_data(self):
        """Test seed data validation."""
        data = {"author": {"name": "Jane", "biography": "Test bio"}, "poem": {"text": "Roses are red"}}

        # Valid case
        is_valid, error = validate_seed_data(data, ["author.name", "poem.text"])
        assert is_valid is True
        assert error is None

        # Missing field
        is_valid, error = validate_seed_data(data, ["author.name", "author.missing"])
        assert is_valid is False
        assert "Missing required field: author.missing" in error

    def test_format_cost(self):
        """Test cost formatting."""
        assert format_cost(12.50) == "$12.50"
        assert format_cost(0.003) == "$0.00"
        assert format_cost(100.999) == "$101.00"

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2025, 11, 19, 10, 30, 0)
        formatted = format_timestamp(dt)
        assert formatted == "2025-11-19T10:30:00"

    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        timestamp_str = "2025-11-19T10:30:00"
        dt = parse_timestamp(timestamp_str)
        assert dt.year == 2025
        assert dt.month == 11
        assert dt.day == 19
        assert dt.hour == 10
        assert dt.minute == 30


class TestConstants:
    """Test constants are properly defined."""

    def test_job_status_enum(self):
        """Test JobStatus enum values."""
        assert JobStatus.QUEUED == "QUEUED"
        assert JobStatus.RUNNING == "RUNNING"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"
        assert JobStatus.BUDGET_EXCEEDED == "BUDGET_EXCEEDED"
        assert JobStatus.CANCELLED == "CANCELLED"

    def test_export_format_enum(self):
        """Test ExportFormat enum values."""
        assert ExportFormat.JSONL == "JSONL"
        assert ExportFormat.PARQUET == "PARQUET"
        assert ExportFormat.CSV == "CSV"

    def test_model_pricing_exists(self):
        """Test model pricing constants are defined."""
        assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in MODEL_PRICING
        assert "meta.llama3-1-8b-instruct-v1:0" in MODEL_PRICING
        assert MODEL_PRICING["meta.llama3-1-8b-instruct-v1:0"]["input"] == 0.30

    def test_checkpoint_interval(self):
        """Test checkpoint interval constant."""
        assert CHECKPOINT_INTERVAL == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
