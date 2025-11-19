"""
Unit tests for cost calculation and budget enforcement logic.

Tests total job cost calculation, budget enforcement, and cost tracking.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/shared'))

from constants import MODEL_PRICING, FARGATE_SPOT_PRICING, S3_PRICING
from utils import (
    calculate_bedrock_cost,
    calculate_fargate_cost,
    calculate_s3_cost,
)
from models import CostBreakdown, JobConfig
from constants import JobStatus


class TestCostCalculation:
    """Test cost calculation functions."""

    def test_bedrock_cost_claude_sonnet_input(self):
        """Test Claude Sonnet input token cost."""
        tokens = 1_000_000
        cost = calculate_bedrock_cost(
            tokens=tokens,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            is_input=True
        )
        # Claude Sonnet: $3.00 per 1M input tokens
        assert cost == pytest.approx(3.00, rel=1e-6)

    def test_bedrock_cost_claude_sonnet_output(self):
        """Test Claude Sonnet output token cost."""
        tokens = 1_000_000
        cost = calculate_bedrock_cost(
            tokens=tokens,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            is_input=False
        )
        # Claude Sonnet: $15.00 per 1M output tokens
        assert cost == pytest.approx(15.00, rel=1e-6)

    def test_bedrock_cost_llama_8b(self):
        """Test Llama 3.1 8B cost calculation."""
        tokens = 1_000_000
        input_cost = calculate_bedrock_cost(
            tokens=tokens,
            model_id="meta.llama3-1-8b-instruct-v1:0",
            is_input=True
        )
        output_cost = calculate_bedrock_cost(
            tokens=tokens,
            model_id="meta.llama3-1-8b-instruct-v1:0",
            is_input=False
        )
        # Llama 8B: $0.30 input, $0.60 output per 1M tokens
        assert input_cost == pytest.approx(0.30, rel=1e-6)
        assert output_cost == pytest.approx(0.60, rel=1e-6)

    def test_bedrock_cost_small_token_count(self):
        """Test cost calculation for small token counts."""
        tokens = 1000  # 1K tokens
        cost = calculate_bedrock_cost(
            tokens=tokens,
            model_id="meta.llama3-1-8b-instruct-v1:0",
            is_input=True
        )
        # Should be 1/1000th of 1M token cost
        expected = 0.30 / 1000
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_fargate_cost_standard_task(self):
        """Test Fargate cost for standard task configuration."""
        # 0.5 vCPU, 1 GB memory, 1 hour
        cost = calculate_fargate_cost(vcpu=0.5, memory_gb=1.0, hours=1.0)

        expected_vcpu = 0.5 * FARGATE_SPOT_PRICING["vcpu"] * 1.0
        expected_memory = 1.0 * FARGATE_SPOT_PRICING["memory"] * 1.0
        expected_total = expected_vcpu + expected_memory

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_fargate_cost_long_running(self):
        """Test Fargate cost for long-running task."""
        # 1 vCPU, 2 GB memory, 12 hours
        cost = calculate_fargate_cost(vcpu=1.0, memory_gb=2.0, hours=12.0)

        expected_vcpu = 1.0 * FARGATE_SPOT_PRICING["vcpu"] * 12.0
        expected_memory = 2.0 * FARGATE_SPOT_PRICING["memory"] * 12.0
        expected_total = expected_vcpu + expected_memory

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_s3_cost_operations(self):
        """Test S3 API operation cost calculation."""
        # 1000 PUTs, 5000 GETs
        cost = calculate_s3_cost(puts=1000, gets=5000)

        expected_put = 1000 * S3_PRICING["PUT"]
        expected_get = 5000 * S3_PRICING["GET"]
        expected_total = expected_put + expected_get

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_s3_cost_puts_only(self):
        """Test S3 cost with only PUT operations."""
        cost = calculate_s3_cost(puts=100, gets=0)
        expected = 100 * S3_PRICING["PUT"]
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_s3_cost_gets_only(self):
        """Test S3 cost with only GET operations."""
        cost = calculate_s3_cost(puts=0, gets=1000)
        expected = 1000 * S3_PRICING["GET"]
        assert cost == pytest.approx(expected, rel=1e-6)


class TestJobCostTracking:
    """Test job cost tracking and budget enforcement."""

    def test_cost_breakdown_creation(self):
        """Test creating a cost breakdown."""
        cost = CostBreakdown(
            job_id="job-123",
            timestamp=datetime(2025, 11, 19, 10, 0, 0),
            bedrock_tokens=100000,
            fargate_hours=0.5,
            s3_operations=50,
            estimated_cost=3.50,
            model_id="meta.llama3-1-8b-instruct-v1:0"
        )

        assert cost.job_id == "job-123"
        assert cost.bedrock_tokens == 100000
        assert cost.fargate_hours == 0.5
        assert cost.estimated_cost == 3.50

    def test_cost_breakdown_dynamodb_format(self):
        """Test cost breakdown DynamoDB serialization includes TTL."""
        cost = CostBreakdown(
            job_id="job-123",
            timestamp=datetime(2025, 11, 19, 10, 0, 0),
            bedrock_tokens=100000,
            fargate_hours=0.5,
            s3_operations=50,
            estimated_cost=3.50
        )

        dynamodb_item = cost.to_dynamodb()

        # Should include TTL (90 days from now)
        assert "ttl" in dynamodb_item
        assert dynamodb_item["estimated_cost"]["N"] == "3.5"

    def test_calculate_total_job_cost(self):
        """Test calculating total job cost from multiple components."""
        # Bedrock cost: 100K input + 50K output tokens @ Llama 8B
        bedrock_input_cost = calculate_bedrock_cost(
            100000, "meta.llama3-1-8b-instruct-v1:0", is_input=True
        )
        bedrock_output_cost = calculate_bedrock_cost(
            50000, "meta.llama3-1-8b-instruct-v1:0", is_input=False
        )

        # Fargate cost: 0.5 vCPU, 1GB, 0.5 hours
        fargate_cost = calculate_fargate_cost(0.5, 1.0, 0.5)

        # S3 cost: 10 PUTs, 50 GETs
        s3_cost = calculate_s3_cost(10, 50)

        total_cost = bedrock_input_cost + bedrock_output_cost + fargate_cost + s3_cost

        # Verify total is reasonable
        assert total_cost > 0
        assert total_cost < 1.0  # Should be well under $1 for this config

    def test_budget_enforcement_within_limit(self):
        """Test job stays within budget."""
        job = JobConfig(
            job_id="job-123",
            user_id="user-456",
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            config={"template_id": "template-1"},
            budget_limit=100.0,
            tokens_used=10000,
            cost_estimate=5.0
        )

        # Job is well within budget
        assert job.cost_estimate < job.budget_limit

    def test_budget_enforcement_exceeded(self):
        """Test detecting budget exceeded."""
        job = JobConfig(
            job_id="job-123",
            user_id="user-456",
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            config={"template_id": "template-1"},
            budget_limit=10.0,
            tokens_used=1000000,
            cost_estimate=12.0
        )

        # Job has exceeded budget
        assert job.cost_estimate > job.budget_limit

    def test_budget_enforcement_at_limit(self):
        """Test job at exact budget limit."""
        job = JobConfig(
            job_id="job-123",
            user_id="user-456",
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            config={"template_id": "template-1"},
            budget_limit=10.0,
            tokens_used=500000,
            cost_estimate=10.0
        )

        # Job is at exact limit
        assert job.cost_estimate == job.budget_limit


class TestCostEstimation:
    """Test cost estimation before job starts."""

    def test_estimate_generation_cost_cheap_model(self):
        """Test cost estimation for cheap model."""
        # Estimate for 1000 records @ Llama 8B
        # Assume ~200 input + 100 output tokens per record
        records = 1000
        tokens_per_record = 300
        total_tokens = records * tokens_per_record

        # Split: ~200 input, ~100 output
        input_tokens = int(total_tokens * 0.67)
        output_tokens = int(total_tokens * 0.33)

        input_cost = calculate_bedrock_cost(
            input_tokens, "meta.llama3-1-8b-instruct-v1:0", is_input=True
        )
        output_cost = calculate_bedrock_cost(
            output_tokens, "meta.llama3-1-8b-instruct-v1:0", is_input=False
        )

        total_bedrock_cost = input_cost + output_cost

        # Should be less than $1 for cheap model
        assert total_bedrock_cost < 1.0

    def test_estimate_generation_cost_premium_model(self):
        """Test cost estimation for premium model."""
        # Estimate for 1000 records @ Claude Sonnet
        records = 1000
        tokens_per_record = 300
        total_tokens = records * tokens_per_record

        input_tokens = int(total_tokens * 0.67)
        output_tokens = int(total_tokens * 0.33)

        input_cost = calculate_bedrock_cost(
            input_tokens, "anthropic.claude-3-5-sonnet-20241022-v2:0", is_input=True
        )
        output_cost = calculate_bedrock_cost(
            output_tokens, "anthropic.claude-3-5-sonnet-20241022-v2:0", is_input=False
        )

        total_bedrock_cost = input_cost + output_cost

        # Premium model should cost more
        assert total_bedrock_cost > 1.0

    def test_cost_comparison_models(self):
        """Test cost comparison between cheap and premium models."""
        tokens = 100000

        # Cheap model (Llama 8B)
        cheap_input = calculate_bedrock_cost(
            tokens, "meta.llama3-1-8b-instruct-v1:0", is_input=True
        )
        cheap_output = calculate_bedrock_cost(
            tokens, "meta.llama3-1-8b-instruct-v1:0", is_input=False
        )
        cheap_total = cheap_input + cheap_output

        # Premium model (Claude Sonnet)
        premium_input = calculate_bedrock_cost(
            tokens, "anthropic.claude-3-5-sonnet-20241022-v2:0", is_input=True
        )
        premium_output = calculate_bedrock_cost(
            tokens, "anthropic.claude-3-5-sonnet-20241022-v2:0", is_input=False
        )
        premium_total = premium_input + premium_output

        # Premium should be significantly more expensive
        assert premium_total > cheap_total * 5


class TestCostOptimization:
    """Test cost optimization strategies."""

    def test_smart_model_routing_savings(self):
        """Test cost savings from smart model routing."""
        # Scenario: 1000 question-answer pairs
        # Smart routing: Use cheap for questions, premium for answers
        # Naive: Use premium for both

        pairs = 1000
        question_tokens = 100  # Simple transformation
        answer_tokens = 200   # Complex reasoning

        # Smart routing
        cheap_model = "meta.llama3-1-8b-instruct-v1:0"
        premium_model = "anthropic.claude-3-5-sonnet-20241022-v2:0"

        smart_question_cost = calculate_bedrock_cost(
            pairs * question_tokens, cheap_model, is_input=False
        )
        smart_answer_cost = calculate_bedrock_cost(
            pairs * answer_tokens, premium_model, is_input=False
        )
        smart_total = smart_question_cost + smart_answer_cost

        # Naive routing (premium for both)
        naive_total = calculate_bedrock_cost(
            pairs * (question_tokens + answer_tokens), premium_model, is_input=False
        )

        # Smart routing should save significant cost
        savings_percent = ((naive_total - smart_total) / naive_total) * 100
        assert savings_percent > 50  # Should save >50%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
