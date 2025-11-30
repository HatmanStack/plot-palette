"""
Extended unit tests for backend data models.

Covers DynamoDB serialization/deserialization and edge cases
to reach >80% coverage target.
"""

import pytest
from datetime import datetime
import json

from backend.shared.models import (
    JobConfig,
    TemplateDefinition,
    TemplateStep,
    CheckpointState,
    CostBreakdown,
    CostComponents,
    QueueItem,
)
from backend.shared.constants import JobStatus, ExportFormat


class TestJobConfigSerialization:
    """Test JobConfig DynamoDB serialization."""

    def test_dict_to_dynamodb_map_with_nested_structures(self):
        """Test complex nested structure serialization."""
        job = JobConfig(
            job_id="test-123",
            user_id="user-456",
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            config={
                "template_id": "template-1",
                "nested_dict": {
                    "level1": {
                        "level2": "value"
                    }
                },
                "list_field": [1, 2, 3],
                "bool_field": True,
                "int_field": 42,
                "float_field": 3.14
            },
            budget_limit=100.0
        )

        dynamodb_item = job.to_dynamodb()

        # Verify nested dict conversion
        assert "M" in dynamodb_item["config"]
        config_map = dynamodb_item["config"]["M"]
        assert "nested_dict" in config_map
        assert "M" in config_map["nested_dict"]

        # Verify list conversion
        assert "list_field" in config_map
        assert "L" in config_map["list_field"]

        # Verify boolean conversion
        assert "bool_field" in config_map
        assert "BOOL" in config_map["bool_field"]
        assert config_map["bool_field"]["BOOL"] is True

    def test_from_dynamodb(self):
        """Test deserializing JobConfig from DynamoDB format."""
        dynamodb_item = {
            "job_id": {"S": "job-123"},
            "user_id": {"S": "user-456"},
            "status": {"S": "RUNNING"},
            "created_at": {"S": "2025-11-19T10:00:00"},
            "updated_at": {"S": "2025-11-19T10:30:00"},
            "config": {
                "M": {
                    "template_id": {"S": "template-1"},
                    "target_records": {"N": "1000"},
                    "nested": {
                        "M": {
                            "field": {"S": "value"}
                        }
                    },
                    "items": {
                        "L": [
                            {"N": "1"},
                            {"N": "2"}
                        ]
                    }
                }
            },
            "budget_limit": {"N": "100.0"},
            "tokens_used": {"N": "50000"},
            "records_generated": {"N": "500"},
            "cost_estimate": {"N": "5.50"}
        }

        job = JobConfig.from_dynamodb(dynamodb_item)

        assert job.job_id == "job-123"
        assert job.user_id == "user-456"
        assert job.status == JobStatus.RUNNING
        assert job.budget_limit == 100.0
        assert job.tokens_used == 50000
        assert job.records_generated == 500
        assert job.cost_estimate == 5.50
        assert job.config["template_id"] == "template-1"
        assert job.config["target_records"] == 1000.0
        assert job.config["nested"]["field"] == "value"


class TestTemplateDefinitionSerialization:
    """Test TemplateDefinition DynamoDB serialization."""

    def test_template_to_dynamodb(self):
        """Test template serialization to DynamoDB."""
        steps = [
            TemplateStep(
                id="step1",
                model="meta.llama3-1-8b-instruct-v1:0",
                prompt="Generate {{ topic }}"
            ),
            TemplateStep(
                id="step2",
                model_tier="premium",
                prompt="Expand {{ steps.step1.output }}"
            )
        ]

        template = TemplateDefinition(
            template_id="template-123",
            version=1,
            name="Test Template",
            user_id="user-456",
            schema_requirements=["topic", "author.name"],
            steps=steps,
            is_public=True,
            created_at=datetime(2025, 11, 19, 10, 0, 0)
        )

        dynamodb_item = template.to_dynamodb()

        assert dynamodb_item["template_id"]["S"] == "template-123"
        assert dynamodb_item["version"]["N"] == "1"
        assert dynamodb_item["name"]["S"] == "Test Template"
        assert dynamodb_item["is_public"]["BOOL"] is True
        assert len(dynamodb_item["schema_requirements"]["L"]) == 2

        # Steps are stored as JSON string
        assert "steps" in dynamodb_item
        assert "S" in dynamodb_item["steps"]
        steps_json = json.loads(dynamodb_item["steps"]["S"])
        assert len(steps_json["steps"]) == 2


class TestCheckpointStateSerialization:
    """Test CheckpointState JSON serialization."""

    def test_checkpoint_roundtrip(self):
        """Test checkpoint serialization and deserialization."""
        original = CheckpointState(
            job_id="job-123",
            records_generated=1000,
            current_batch=20,
            tokens_used=500000,
            cost_accumulated=12.50,
            last_updated=datetime(2025, 11, 19, 10, 30, 0),
            resume_state={
                "seed_index": 42,
                "step": "answer",
                "partial_data": [1, 2, 3]
            }
        )

        # Serialize
        json_str = original.to_json()

        # Deserialize
        restored = CheckpointState.from_json(json_str, etag="etag-abc")

        assert restored.job_id == original.job_id
        assert restored.records_generated == original.records_generated
        assert restored.current_batch == original.current_batch
        assert restored.tokens_used == original.tokens_used
        assert restored.cost_accumulated == original.cost_accumulated
        assert restored.resume_state == original.resume_state
        assert restored.etag == "etag-abc"


class TestCostBreakdownTTL:
    """Test CostBreakdown TTL handling."""

    def test_cost_breakdown_includes_ttl(self):
        """Test that TTL is calculated and included."""
        cost = CostBreakdown(
            job_id="job-123",
            timestamp=datetime.utcnow(),
            bedrock_tokens=100000,
            fargate_hours=1.0,
            s3_operations=50,
            estimated_cost=CostComponents(bedrock=4.0, fargate=0.5, s3=0.5, total=5.0),
            model_id="meta.llama3-1-8b-instruct-v1:0"
        )

        dynamodb_item = cost.to_dynamodb()

        # Should have TTL field
        assert "ttl" in dynamodb_item
        assert "N" in dynamodb_item["ttl"]

        # TTL should be a Unix timestamp
        ttl_value = int(dynamodb_item["ttl"]["N"])
        assert ttl_value > 0

        # Should be approximately 90 days from now
        import time
        current_time = int(time.time())
        expected_ttl = current_time + (90 * 24 * 60 * 60)

        # Allow 1 day variance (test may run on different timezone)
        assert abs(ttl_value - expected_ttl) < 86400

    def test_cost_breakdown_without_model_id(self):
        """Test cost breakdown without optional model_id."""
        cost = CostBreakdown(
            job_id="job-123",
            timestamp=datetime.utcnow(),
            bedrock_tokens=0,
            fargate_hours=0.5,
            s3_operations=10,
            estimated_cost=CostComponents(bedrock=0.0, fargate=0.04, s3=0.01, total=0.05)
        )

        dynamodb_item = cost.to_dynamodb()

        # model_id should not be in item
        assert "model_id" not in dynamodb_item or dynamodb_item["model_id"]["S"] == ""


class TestQueueItemCompositeKey:
    """Test QueueItem composite key generation."""

    def test_queue_item_composite_key_format(self):
        """Test composite key format is correct."""
        timestamp = datetime(2025, 11, 19, 10, 30, 45)
        item = QueueItem(
            status=JobStatus.QUEUED,
            job_id="job-123",
            timestamp=timestamp,
            priority=5
        )

        composite_key = item.job_id_timestamp

        # Format should be job-id#timestamp
        assert composite_key == f"job-123#{timestamp.isoformat()}"
        assert "#" in composite_key
        assert composite_key.startswith("job-123#")

    def test_queue_item_to_dynamodb(self):
        """Test QueueItem DynamoDB serialization."""
        item = QueueItem(
            status=JobStatus.RUNNING,
            job_id="job-456",
            timestamp=datetime.utcnow(),
            priority=10,
            task_arn="arn:aws:ecs:us-east-1:123456789:task/abc123"
        )

        dynamodb_item = item.to_dynamodb()

        assert dynamodb_item["status"]["S"] == "RUNNING"
        assert dynamodb_item["job_id"]["S"] == "job-456"
        assert dynamodb_item["priority"]["N"] == "10"
        assert dynamodb_item["task_arn"]["S"] == "arn:aws:ecs:us-east-1:123456789:task/abc123"

        # Composite key should be present
        assert "job_id_timestamp" in dynamodb_item

    def test_queue_item_without_task_arn(self):
        """Test QueueItem without optional task_arn."""
        item = QueueItem(
            status=JobStatus.QUEUED,
            job_id="job-789",
            timestamp=datetime.utcnow(),
            priority=0
        )

        dynamodb_item = item.to_dynamodb()

        # task_arn should not be in item if None
        assert "task_arn" not in dynamodb_item


class TestTemplateStepValidation:
    """Test TemplateStep validation."""

    def test_valid_model_tiers(self):
        """Test all valid model tier values."""
        valid_tiers = ["tier-1", "tier-2", "tier-3", "cheap", "balanced", "premium"]

        for tier in valid_tiers:
            step = TemplateStep(
                id="step1",
                model_tier=tier,
                prompt="Test prompt"
            )
            assert step.model_tier == tier

    def test_invalid_model_tier(self):
        """Test that invalid model tier raises ValueError."""
        with pytest.raises(ValueError, match="Invalid model tier"):
            TemplateStep(
                id="step1",
                model_tier="invalid-tier",
                prompt="Test prompt"
            )

    def test_step_with_both_model_and_tier(self):
        """Test step can have both model and tier (tier ignored)."""
        step = TemplateStep(
            id="step1",
            model="meta.llama3-1-8b-instruct-v1:0",
            model_tier="premium",  # Should be ignored when model specified
            prompt="Test prompt"
        )

        assert step.model == "meta.llama3-1-8b-instruct-v1:0"
        assert step.model_tier == "premium"

    def test_step_with_neither_model_nor_tier(self):
        """Test step can be created without model or tier (will use default)."""
        step = TemplateStep(
            id="step1",
            prompt="Test prompt"
        )

        assert step.model is None
        assert step.model_tier is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
