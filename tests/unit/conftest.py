"""
Plot Palette - Unit Test Fixtures

Fixtures specific to unit tests, including sample model instances
and mock configurations.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from backend.shared.constants import JobStatus


@pytest.fixture
def sample_job_config() -> Dict[str, Any]:
    """Sample job configuration for testing."""
    return {
        "job_id": "test-job-123",
        "user_id": "test-user-456",
        "status": JobStatus.QUEUED,
        "created_at": datetime(2025, 11, 19, 10, 0, 0),
        "updated_at": datetime(2025, 11, 19, 10, 0, 0),
        "config": {
            "template_id": "template-789",
            "seed_data_path": "s3://test-bucket/seed-data/test.json",
            "output_format": "JSONL",
        },
        "budget_limit": 100.0,
        "tokens_used": 0,
        "records_generated": 0,
        "cost_estimate": 0.0,
    }


@pytest.fixture
def sample_template() -> Dict[str, Any]:
    """Sample template definition for testing."""
    return {
        "template_id": "template-123",
        "version": 1,
        "name": "Test Template",
        "user_id": "test-user-456",
        "schema_requirements": ["author.name", "author.biography"],
        "steps": [
            {
                "id": "question",
                "model": "meta.llama3-1-8b-instruct-v1:0",
                "prompt": "Generate a question about {{ author.name }}"
            },
            {
                "id": "answer",
                "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "prompt": "Answer: {{ steps.question.output }}"
            }
        ],
        "is_public": False,
        "created_at": datetime(2025, 11, 19, 10, 0, 0),
    }


@pytest.fixture
def sample_checkpoint() -> Dict[str, Any]:
    """Sample checkpoint state for testing."""
    return {
        "job_id": "test-job-123",
        "records_generated": 500,
        "current_batch": 10,
        "tokens_used": 100000,
        "cost_accumulated": 2.50,
        "last_updated": datetime(2025, 11, 19, 11, 30, 0),
        "resume_state": {
            "seed_data_index": 500,
            "current_step": "answer",
        },
        "etag": "test-etag-abc123",
    }


@pytest.fixture
def sample_seed_data() -> Dict[str, Any]:
    """Sample seed data for template rendering."""
    return {
        "author": {
            "name": "Emily Dickinson",
            "biography": "American poet known for unconventional style and reclusive nature.",
            "genre": "poetry",
        },
        "poem": {
            "title": "Hope is the thing with feathers",
            "text": "Hope is the thing with feathers that perches in the soul...",
        }
    }


@pytest.fixture
def sample_cost_breakdown() -> Dict[str, Any]:
    """Sample cost breakdown for testing."""
    return {
        "job_id": "test-job-123",
        "timestamp": datetime(2025, 11, 19, 12, 0, 0),
        "bedrock_tokens": 150000,
        "fargate_hours": 0.5,
        "s3_operations": 100,
        "estimated_cost": {
            "bedrock": 3.75,
            "fargate": 0.25,
            "s3": 0.05,
            "total": 4.05,
        },
        "model_id": "meta.llama3-1-8b-instruct-v1:0",
    }


@pytest.fixture
def sample_queue_item() -> Dict[str, Any]:
    """Sample queue item for testing."""
    return {
        "status": JobStatus.QUEUED,
        "job_id": "test-job-123",
        "timestamp": datetime(2025, 11, 19, 10, 0, 0),
        "priority": 0,
        "task_arn": None,
    }
