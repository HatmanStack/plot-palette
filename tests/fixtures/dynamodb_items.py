"""
DynamoDB Item Factories

Factory functions for creating properly typed DynamoDB items
that match the application's table schemas.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json


def make_job_item(
    job_id: str = "test-job-123",
    user_id: str = "test-user-456",
    status: str = "QUEUED",
    template_id: str = "template-789",
    budget_limit: float = 100.0,
    num_records: int = 1000,
    tokens_used: int = 0,
    records_generated: int = 0,
    cost_estimate: float = 0.0,
    execution_arn: Optional[str] = None,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Create a DynamoDB Jobs table item.

    Args:
        job_id: Unique job identifier
        user_id: User who created the job
        status: Job status (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED)
        template_id: Template used for generation
        budget_limit: Budget limit in USD
        num_records: Target number of records
        tokens_used: Total tokens consumed
        records_generated: Records generated so far
        cost_estimate: Estimated cost in USD
        created_at: Creation timestamp
        updated_at: Last update timestamp
        **overrides: Additional fields to override

    Returns:
        DynamoDB item dictionary with AttributeValue format
    """
    now = datetime.now(timezone.utc)
    created = created_at or now
    updated = updated_at or now

    item = {
        "job_id": {"S": job_id},
        "user_id": {"S": user_id},
        "status": {"S": status},
        "created_at": {"S": created.isoformat()},
        "updated_at": {"S": updated.isoformat()},
        "config": {
            "M": {
                "template_id": {"S": template_id},
                "seed_data_path": {"S": f"s3://test-bucket/seed-data/{job_id}.json"},
                "output_format": {"S": "JSONL"},
            }
        },
        "budget_limit": {"N": str(budget_limit)},
        "num_records": {"N": str(num_records)},
        "tokens_used": {"N": str(tokens_used)},
        "records_generated": {"N": str(records_generated)},
        "cost_estimate": {"N": str(cost_estimate)},
    }

    if execution_arn:
        item["execution_arn"] = {"S": execution_arn}

    # Apply any overrides
    for key, value in overrides.items():
        if isinstance(value, str):
            item[key] = {"S": value}
        elif isinstance(value, bool):
            item[key] = {"BOOL": value}
        elif isinstance(value, (int, float)):
            item[key] = {"N": str(value)}
        elif isinstance(value, dict):
            item[key] = value  # Assume already in DynamoDB format

    return item


def make_template_item(
    template_id: str = "template-123",
    user_id: str = "test-user-456",
    name: str = "Test Template",
    version: int = 1,
    steps: Optional[list] = None,
    schema_requirements: Optional[list] = None,
    is_public: bool = False,
    created_at: Optional[datetime] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Create a DynamoDB Templates table item.

    Args:
        template_id: Unique template identifier
        user_id: User who created the template
        name: Template display name
        version: Template version number
        steps: Template steps definition
        schema_requirements: Required fields in seed data
        is_public: Whether template is publicly shareable
        created_at: Creation timestamp
        **overrides: Additional fields to override

    Returns:
        DynamoDB item dictionary with AttributeValue format
    """
    now = created_at or datetime.now(timezone.utc)

    default_steps = steps or [
        {
            "id": "question",
            "model": "meta.llama3-1-8b-instruct-v1:0",
            "prompt": "Generate a question about {{ author.name }}"
        }
    ]

    default_requirements = schema_requirements or ["author.name"]

    # Create template definition for storage
    template_def = {
        "template_id": template_id,
        "version": version,
        "name": name,
        "user_id": user_id,
        "schema_requirements": default_requirements,
        "steps": default_steps,
        "is_public": is_public,
        "created_at": now.isoformat(),
    }

    item = {
        "template_id": {"S": template_id},
        "user_id": {"S": user_id},
        "name": {"S": name},
        "version": {"N": str(version)},
        "schema_requirements": {"L": [{"S": req} for req in default_requirements]},
        "steps": {"S": json.dumps(template_def)},
        "is_public": {"BOOL": is_public},
        "created_at": {"S": now.isoformat()},
    }

    # Apply overrides
    for key, value in overrides.items():
        if isinstance(value, str):
            item[key] = {"S": value}
        elif isinstance(value, bool):
            item[key] = {"BOOL": value}
        elif isinstance(value, (int, float)):
            item[key] = {"N": str(value)}
        elif isinstance(value, dict):
            item[key] = value

    return item


def make_queue_item(
    job_id: str = "test-job-123",
    status: str = "QUEUED",
    priority: int = 0,
    task_arn: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Create a DynamoDB Queue table item.

    Args:
        job_id: Job identifier
        status: Queue status (QUEUED, RUNNING, COMPLETED)
        priority: Job priority (higher = more urgent)
        task_arn: ECS task ARN when running
        timestamp: Queue entry timestamp
        **overrides: Additional fields to override

    Returns:
        DynamoDB item dictionary with AttributeValue format
    """
    now = timestamp or datetime.now(timezone.utc)
    job_id_timestamp = f"{job_id}#{now.isoformat()}"

    item = {
        "status": {"S": status},
        "job_id_timestamp": {"S": job_id_timestamp},
        "job_id": {"S": job_id},
        "priority": {"N": str(priority)},
    }

    if task_arn:
        item["task_arn"] = {"S": task_arn}

    # Apply overrides
    for key, value in overrides.items():
        if isinstance(value, str):
            item[key] = {"S": value}
        elif isinstance(value, bool):
            item[key] = {"BOOL": value}
        elif isinstance(value, (int, float)):
            item[key] = {"N": str(value)}
        elif isinstance(value, dict):
            item[key] = value

    return item


def make_checkpoint_item(
    job_id: str = "test-job-123",
    records_generated: int = 500,
    current_batch: int = 10,
    tokens_used: int = 100000,
    cost_accumulated: float = 2.50,
    last_updated: Optional[datetime] = None,
    resume_state: Optional[Dict[str, Any]] = None,
    etag: str = "test-etag-abc123",
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Create a checkpoint state dictionary (stored in S3 as JSON).

    Note: Checkpoints are stored in S3, not DynamoDB. This returns
    the JSON-serializable checkpoint data.

    Args:
        job_id: Job identifier
        records_generated: Total records generated so far
        current_batch: Current batch number
        tokens_used: Total tokens consumed
        cost_accumulated: Cost accumulated in USD
        last_updated: Last checkpoint timestamp
        resume_state: Custom state for resuming generation
        etag: S3 ETag for concurrency control
        **overrides: Additional fields to override

    Returns:
        Checkpoint state dictionary (for S3 storage)
    """
    now = last_updated or datetime.now(timezone.utc)

    checkpoint = {
        "job_id": job_id,
        "records_generated": records_generated,
        "current_batch": current_batch,
        "tokens_used": tokens_used,
        "cost_accumulated": cost_accumulated,
        "last_updated": now.isoformat(),
        "resume_state": resume_state or {
            "seed_data_index": records_generated,
            "current_step": "answer",
        },
    }

    # Apply overrides
    checkpoint.update(overrides)

    # Store etag separately (not part of the JSON content)
    checkpoint["_etag"] = etag

    return checkpoint


def make_cost_breakdown_item(
    job_id: str = "test-job-123",
    bedrock_tokens: int = 150000,
    fargate_hours: float = 0.5,
    s3_operations: int = 100,
    bedrock_cost: float = 3.75,
    fargate_cost: float = 0.25,
    s3_cost: float = 0.05,
    total_cost: float = 4.05,
    model_id: str = "meta.llama3-1-8b-instruct-v1:0",
    timestamp: Optional[datetime] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Create a DynamoDB CostBreakdown item.

    Args:
        job_id: Job identifier
        bedrock_tokens: Tokens consumed by Bedrock
        fargate_hours: Fargate compute hours
        s3_operations: S3 API operation count
        bedrock_cost: Bedrock cost component
        fargate_cost: Fargate cost component
        s3_cost: S3 cost component
        total_cost: Total combined cost
        model_id: Model used for this period
        timestamp: Measurement timestamp
        **overrides: Additional fields to override

    Returns:
        DynamoDB item dictionary with AttributeValue format
    """
    now = timestamp or datetime.now(timezone.utc)
    ttl = int(now.timestamp() + (90 * 24 * 60 * 60))  # 90 days

    item = {
        "job_id": {"S": job_id},
        "timestamp": {"S": now.isoformat()},
        "bedrock_tokens": {"N": str(bedrock_tokens)},
        "fargate_hours": {"N": str(fargate_hours)},
        "s3_operations": {"N": str(s3_operations)},
        "estimated_cost": {
            "M": {
                "bedrock": {"N": str(bedrock_cost)},
                "fargate": {"N": str(fargate_cost)},
                "s3": {"N": str(s3_cost)},
                "total": {"N": str(total_cost)},
            }
        },
        "model_id": {"S": model_id},
        "ttl": {"N": str(ttl)},
    }

    # Apply overrides
    for key, value in overrides.items():
        if isinstance(value, str):
            item[key] = {"S": value}
        elif isinstance(value, bool):
            item[key] = {"BOOL": value}
        elif isinstance(value, (int, float)):
            item[key] = {"N": str(value)}
        elif isinstance(value, dict):
            item[key] = value

    return item
