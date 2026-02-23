"""
Plot Palette - Pydantic Data Models

This module defines type-safe data models for jobs, templates, checkpoints,
and cost tracking using Pydantic for validation and serialization.
"""

import ipaddress
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, NotRequired, TypedDict
from urllib.parse import urlparse

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import BatchStatus, JobStatus, QualityStatus

_serializer = TypeSerializer()
_deserializer = TypeDeserializer()


# TypedDict definitions for strongly-typed dictionaries
class TemplateStepDict(TypedDict):
    """Type definition for a template step configuration."""

    id: str
    prompt: str
    model: NotRequired[str]
    model_tier: NotRequired[str]


class TemplateDefinitionDict(TypedDict):
    """Type definition for a complete template definition."""

    steps: list[TemplateStepDict]


class JobConfigDict(TypedDict, total=False):
    """
    Type definition for job configuration.

    All fields are optional to maintain backward compatibility with
    existing tests and code that may pass partial configs.
    """

    template_id: str
    seed_data_path: str
    budget_limit: float
    output_format: str
    num_records: int
    template_version: int
    partition_strategy: str
    priority: int


class ResumeStateDict(TypedDict, total=False):
    """Type definition for checkpoint resume state."""

    last_seed_index: int
    partial_results: dict[str, Any]
    step_outputs: dict[str, str]


class JobConfig(BaseModel):
    """Job configuration and state model matching DynamoDB Jobs table schema."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="Unique job identifier (UUID)")
    user_id: str = Field(..., description="User who created the job")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Current job status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Job creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )
    config: dict[str, Any] = Field(..., description="Job configuration dictionary")
    budget_limit: float = Field(..., gt=0, description="Budget limit in USD")
    tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed")
    records_generated: int = Field(default=0, ge=0, description="Number of records generated")
    cost_estimate: float = Field(default=0.0, ge=0, description="Estimated cost in USD")
    execution_arn: str | None = Field(None, description="Step Functions execution ARN")

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "JobConfig":
        """Validate cross-field consistency."""
        if self.status == JobStatus.COMPLETED and self.records_generated == 0:
            raise ValueError("COMPLETED job must have records_generated > 0")
        return self

    def to_dynamodb(self) -> dict[str, Any]:
        """Convert to low-level DynamoDB item format (for client.put_item)."""
        item = {
            "job_id": {"S": self.job_id},
            "user_id": {"S": self.user_id},
            "status": {"S": self.status.value},
            "created_at": {"S": self.created_at.isoformat()},
            "updated_at": {"S": self.updated_at.isoformat()},
            "config": {"M": self._dict_to_dynamodb_map(self.config)},
            "budget_limit": {"N": str(self.budget_limit)},
            "tokens_used": {"N": str(self.tokens_used)},
            "records_generated": {"N": str(self.records_generated)},
            "cost_estimate": {"N": str(self.cost_estimate)},
        }
        if self.execution_arn:
            item["execution_arn"] = {"S": self.execution_arn}
        return item

    def to_table_item(self) -> dict[str, Any]:
        """Convert to high-level DynamoDB item format (for Table.put_item)."""
        item = {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "config": self._convert_floats(self.config),
            "budget_limit": Decimal(str(self.budget_limit)),
            "tokens_used": self.tokens_used,
            "records_generated": self.records_generated,
            "cost_estimate": Decimal(str(self.cost_estimate)),
        }
        if self.execution_arn:
            item["execution_arn"] = self.execution_arn
        return item

    @staticmethod
    def _convert_floats(obj: Any) -> Any:
        """Convert float values to Decimal (required by DynamoDB)."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        if isinstance(obj, dict):
            return {k: JobConfig._convert_floats(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [JobConfig._convert_floats(i) for i in obj]
        return obj

    @staticmethod
    def _dict_to_dynamodb_map(d: dict[str, Any]) -> dict[str, Any]:
        """Convert Python dict to DynamoDB Map format using boto3 TypeSerializer."""
        return {k: _serializer.serialize(JobConfig._convert_floats(v)) for k, v in d.items()}

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "JobConfig":
        """Create JobConfig from DynamoDB item."""
        return cls(
            job_id=item["job_id"]["S"],
            user_id=item["user_id"]["S"],
            status=JobStatus(item["status"]["S"]),
            created_at=datetime.fromisoformat(item["created_at"]["S"]),
            updated_at=datetime.fromisoformat(item["updated_at"]["S"]),
            config=cls._dynamodb_map_to_dict(item["config"]["M"]),
            budget_limit=float(item["budget_limit"]["N"]),
            tokens_used=int(item["tokens_used"]["N"]),
            records_generated=int(item["records_generated"]["N"]),
            cost_estimate=float(item["cost_estimate"]["N"]),
            execution_arn=item.get("execution_arn", {}).get("S"),
        )

    @staticmethod
    def _dynamodb_map_to_dict(m: dict[str, Any]) -> dict[str, Any]:
        """Convert DynamoDB Map to Python dict using boto3 TypeDeserializer."""

        def _convert_decimals(obj: Any) -> Any:
            if isinstance(obj, Decimal):
                return int(obj) if obj == int(obj) else float(obj)
            if isinstance(obj, dict):
                return {k: _convert_decimals(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_convert_decimals(i) for i in obj]
            return obj

        return {k: _convert_decimals(_deserializer.deserialize(v)) for k, v in m.items()}


class TemplateStep(BaseModel):
    """Single step in a multi-step template."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Step identifier")
    model: str | None = Field(None, description="Specific model ID to use")
    model_tier: str | None = Field(None, description="Model tier (tier-1, tier-2, tier-3)")
    prompt: str = Field(..., description="Jinja2 prompt template")

    @field_validator("model_tier")
    @classmethod
    def validate_model_tier(cls, v):
        """Validate model tier if provided."""
        if v is not None and v not in [
            "tier-1",
            "tier-2",
            "tier-3",
            "cheap",
            "balanced",
            "premium",
        ]:
            raise ValueError(f"Invalid model tier: {v}")
        return v


class TemplateDefinition(BaseModel):
    """Prompt template definition for generation jobs."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., description="Unique template identifier (UUID)")
    version: int = Field(default=1, ge=1, description="Template version number")
    name: str = Field(..., min_length=1, max_length=200, description="Template display name")
    user_id: str = Field(..., description="User who created the template")
    schema_requirements: list[str] = Field(
        default_factory=list,
        description="Required fields in seed data (e.g., ['author.biography', 'poem.text'])",
    )
    steps: list[TemplateStep] = Field(..., min_length=1, description="Generation steps")
    is_public: bool = Field(default=False, description="Whether template is shareable")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )

    def to_dynamodb(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "template_id": {"S": self.template_id},
            "version": {"N": str(self.version)},
            "name": {"S": self.name},
            "user_id": {"S": self.user_id},
            "schema_requirements": {"L": [{"S": req} for req in self.schema_requirements]},
            "steps": {"S": self.model_dump_json()},  # Store as JSON string
            "is_public": {"BOOL": self.is_public},
            "created_at": {"S": self.created_at.isoformat()},
        }

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "TemplateDefinition":
        """Create TemplateDefinition from DynamoDB item."""
        # Parse the full template from the stored JSON
        template_data = cls.model_validate_json(item["steps"]["S"])
        # Override with DynamoDB-stored metadata
        template_data.template_id = item["template_id"]["S"]
        template_data.version = int(item["version"]["N"])
        template_data.name = item["name"]["S"]
        template_data.user_id = item["user_id"]["S"]
        template_data.schema_requirements = [
            req["S"] for req in item.get("schema_requirements", {}).get("L", [])
        ]
        template_data.is_public = item.get("is_public", {}).get("BOOL", False)
        template_data.created_at = datetime.fromisoformat(item["created_at"]["S"])
        return template_data


class CheckpointState(BaseModel):
    """Checkpoint state for job recovery after spot interruptions."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="Job identifier")
    records_generated: int = Field(default=0, ge=0, description="Total records generated so far")
    current_batch: int = Field(default=0, ge=0, description="Current batch number")
    tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed")
    cost_accumulated: float = Field(default=0.0, ge=0, description="Cost accumulated in USD")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last checkpoint timestamp"
    )
    resume_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom state for resuming generation",
    )
    etag: str | None = Field(None, description="S3 ETag for concurrency control")

    def to_json(self) -> str:
        """Serialize to JSON for S3 storage."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str, etag: str | None = None) -> "CheckpointState":
        """Deserialize from JSON."""
        checkpoint = cls.model_validate_json(json_str)
        checkpoint.etag = etag
        return checkpoint


class CostComponents(BaseModel):
    """Breakdown of costs by service."""

    model_config = ConfigDict(extra="forbid")

    bedrock: float = Field(default=0.0, ge=0, description="Bedrock API costs")
    fargate: float = Field(default=0.0, ge=0, description="Fargate compute costs")
    s3: float = Field(default=0.0, ge=0, description="S3 storage/operations costs")
    total: float = Field(default=0.0, ge=0, description="Total combined cost")


class CostBreakdown(BaseModel):
    """Cost breakdown for a specific time period."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="Job identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Measurement timestamp"
    )
    bedrock_tokens: int = Field(default=0, ge=0, description="Tokens consumed by Bedrock")
    fargate_hours: float = Field(default=0.0, ge=0, description="Fargate compute hours")
    s3_operations: int = Field(default=0, ge=0, description="S3 API operation count")
    estimated_cost: CostComponents = Field(
        default_factory=CostComponents, description="Cost breakdown by service"
    )
    model_id: str | None = Field(None, description="Model used for this period")

    def to_dynamodb(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            "job_id": {"S": self.job_id},
            "timestamp": {"S": self.timestamp.isoformat()},
            "bedrock_tokens": {"N": str(self.bedrock_tokens)},
            "fargate_hours": {"N": str(self.fargate_hours)},
            "s3_operations": {"N": str(self.s3_operations)},
            "estimated_cost": {
                "M": {
                    "bedrock": {"N": str(self.estimated_cost.bedrock)},
                    "fargate": {"N": str(self.estimated_cost.fargate)},
                    "s3": {"N": str(self.estimated_cost.s3)},
                    "total": {"N": str(self.estimated_cost.total)},
                }
            },
        }
        if self.model_id:
            item["model_id"] = {"S": self.model_id}

        # Add TTL (90 days from now)
        ttl = int(datetime.now(UTC).timestamp() + (90 * 24 * 60 * 60))
        item["ttl"] = {"N": str(ttl)}

        return item

    def to_table_item(self) -> dict[str, Any]:
        """Convert to high-level DynamoDB item format (for Table.put_item)."""
        item: dict[str, Any] = {
            "job_id": self.job_id,
            "timestamp": self.timestamp.isoformat(),
            "bedrock_tokens": self.bedrock_tokens,
            "fargate_hours": Decimal(str(self.fargate_hours)),
            "s3_operations": self.s3_operations,
            "estimated_cost": {
                "bedrock": Decimal(str(self.estimated_cost.bedrock)),
                "fargate": Decimal(str(self.estimated_cost.fargate)),
                "s3": Decimal(str(self.estimated_cost.s3)),
                "total": Decimal(str(self.estimated_cost.total)),
            },
        }
        if self.model_id:
            item["model_id"] = self.model_id

        # Add TTL (90 days from now)
        ttl = int(datetime.now(UTC).timestamp() + (90 * 24 * 60 * 60))
        item["ttl"] = ttl

        return item

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "CostBreakdown":
        """Create CostBreakdown from DynamoDB item."""
        cost_map = item.get("estimated_cost", {}).get("M", {})
        return cls(
            job_id=item["job_id"]["S"],
            timestamp=datetime.fromisoformat(item["timestamp"]["S"]),
            bedrock_tokens=int(item["bedrock_tokens"]["N"]),
            fargate_hours=float(item["fargate_hours"]["N"]),
            s3_operations=int(item["s3_operations"]["N"]),
            estimated_cost=CostComponents(
                bedrock=float(cost_map.get("bedrock", {}).get("N", "0.0")),
                fargate=float(cost_map.get("fargate", {}).get("N", "0.0")),
                s3=float(cost_map.get("s3", {}).get("N", "0.0")),
                total=float(cost_map.get("total", {}).get("N", "0.0")),
            ),
            model_id=item.get("model_id", {}).get("S"),
        )


class NotificationPreferences(BaseModel):
    """Per-user notification preferences for job status alerts."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., description="User identifier")
    email_enabled: bool = Field(default=False, description="Whether email notifications are enabled")
    email_address: str | None = Field(None, description="Email address for notifications")
    webhook_enabled: bool = Field(default=False, description="Whether webhook notifications are enabled")
    webhook_url: str | None = Field(None, description="Webhook URL for notifications (HTTPS only)")
    notify_on_complete: bool = Field(default=True, description="Notify when job completes")
    notify_on_failure: bool = Field(default=True, description="Notify when job fails")
    notify_on_budget_exceeded: bool = Field(default=True, description="Notify when budget exceeded")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v):
        """Webhook URL must be HTTPS and not target private/reserved IP ranges."""
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must start with https://")
        parsed = urlparse(v)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Webhook URL must have a valid hostname")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                raise ValueError("Webhook URL must not target private or reserved IP addresses")
        except ValueError as err:
            if "must not" in str(err):
                raise
            # hostname is not an IP literal -- it's a DNS name, allow it
        return v

    def to_table_item(self) -> dict[str, Any]:
        """Convert to high-level DynamoDB item format (for Table.put_item)."""
        item: dict[str, Any] = {
            "user_id": self.user_id,
            "email_enabled": self.email_enabled,
            "webhook_enabled": self.webhook_enabled,
            "notify_on_complete": self.notify_on_complete,
            "notify_on_failure": self.notify_on_failure,
            "notify_on_budget_exceeded": self.notify_on_budget_exceeded,
            "updated_at": self.updated_at.isoformat(),
        }
        if self.email_address is not None:
            item["email_address"] = self.email_address
        if self.webhook_url is not None:
            item["webhook_url"] = self.webhook_url
        return item

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "NotificationPreferences":
        """Create NotificationPreferences from DynamoDB table item."""
        return cls(
            user_id=item["user_id"],
            email_enabled=item.get("email_enabled", False),
            email_address=item.get("email_address"),
            webhook_enabled=item.get("webhook_enabled", False),
            webhook_url=item.get("webhook_url"),
            notify_on_complete=item.get("notify_on_complete", True),
            notify_on_failure=item.get("notify_on_failure", True),
            notify_on_budget_exceeded=item.get("notify_on_budget_exceeded", True),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    @classmethod
    def defaults(cls, user_id: str) -> "NotificationPreferences":
        """Return default preferences for a user with no saved preferences."""
        return cls(user_id=user_id)


class BatchConfig(BaseModel):
    """Batch configuration for tracking groups of related jobs."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(..., description="Unique batch identifier (UUID)")
    user_id: str = Field(..., description="User who created the batch")
    name: str = Field(..., min_length=1, max_length=200, description="Batch display name")
    status: BatchStatus = Field(default=BatchStatus.PENDING, description="Current batch status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Batch creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )
    job_ids: list[str] = Field(default_factory=list, description="References to individual jobs")
    total_jobs: int = Field(..., ge=1, description="Total number of jobs in batch")
    completed_jobs: int = Field(default=0, ge=0, description="Number of completed jobs")
    failed_jobs: int = Field(default=0, ge=0, description="Number of failed jobs")
    template_id: str = Field(..., description="Template used for all jobs")
    template_version: int = Field(..., ge=1, description="Template version used")
    sweep_config: dict[str, Any] = Field(
        default_factory=dict, description="What was varied (model_tiers, seed_data_paths, etc.)"
    )
    total_cost: float = Field(default=0.0, ge=0, description="Aggregate cost across all jobs")

    def to_table_item(self) -> dict[str, Any]:
        """Convert to high-level DynamoDB item format (for Table.put_item)."""
        return {
            "batch_id": self.batch_id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "job_ids": self.job_ids,
            "total_jobs": self.total_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "sweep_config": self.sweep_config,
            "total_cost": Decimal(str(self.total_cost)),
        }

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "BatchConfig":
        """Create BatchConfig from DynamoDB table item."""
        return cls(
            batch_id=item["batch_id"],
            user_id=item["user_id"],
            name=item["name"],
            status=BatchStatus(item["status"]),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            job_ids=item.get("job_ids", []),
            total_jobs=int(item["total_jobs"]),
            completed_jobs=int(item.get("completed_jobs", 0)),
            failed_jobs=int(item.get("failed_jobs", 0)),
            template_id=item["template_id"],
            template_version=int(item["template_version"]),
            sweep_config=item.get("sweep_config", {}),
            total_cost=float(item.get("total_cost", 0)),
        )


class QueueItem(BaseModel):
    """Queue item for job scheduling."""

    model_config = ConfigDict(extra="forbid")

    status: JobStatus = Field(..., description="Queue status (QUEUED, RUNNING, COMPLETED)")
    job_id: str = Field(..., description="Job identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Queue entry timestamp"
    )
    priority: int = Field(default=0, description="Priority (higher = more urgent)")
    task_arn: str | None = Field(None, description="ECS task ARN when running")

    @property
    def job_id_timestamp(self) -> str:
        """Composite sort key for DynamoDB."""
        return f"{self.job_id}#{self.timestamp.isoformat()}"

    def to_dynamodb(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            "status": {"S": self.status.value},
            "job_id_timestamp": {"S": self.job_id_timestamp},
            "job_id": {"S": self.job_id},
            "priority": {"N": str(self.priority)},
        }
        if self.task_arn:
            item["task_arn"] = {"S": self.task_arn}
        return item

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "QueueItem":
        """Create QueueItem from DynamoDB item."""
        # Extract timestamp from composite key
        job_id_timestamp = item["job_id_timestamp"]["S"]
        _, timestamp_str = job_id_timestamp.split("#", 1)

        return cls(
            status=JobStatus(item["status"]["S"]),
            job_id=item["job_id"]["S"],
            timestamp=datetime.fromisoformat(timestamp_str),
            priority=int(item.get("priority", {}).get("N", "0")),
            task_arn=item.get("task_arn", {}).get("S"),
        )


class RecordScore(BaseModel):
    """Quality score for a single generated record."""

    model_config = ConfigDict(extra="forbid")

    record_index: int = Field(..., ge=0, description="Index of the record in the sample")
    coherence: float = Field(..., ge=0.0, le=1.0, description="Coherence score (0.0-1.0)")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0.0-1.0)")
    format_compliance: float = Field(
        ..., ge=0.0, le=1.0, description="Format compliance score (0.0-1.0)"
    )
    detail: str = Field(default="", description="Brief rationale from the scoring LLM")


class QualityMetrics(BaseModel):
    """Quality scoring results for a completed job."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="Job identifier")
    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When scoring was performed"
    )
    sample_size: int = Field(..., ge=0, description="Number of records sampled for scoring")
    total_records: int = Field(..., ge=0, description="Total records in the job output")
    model_used_for_scoring: str = Field(
        ..., description="Which LLM performed the scoring"
    )
    aggregate_scores: dict[str, float] = Field(
        default_factory=dict, description="Mean scores per dimension"
    )
    diversity_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Diversity score (0.0-1.0)"
    )
    overall_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Weighted average of all dimensions"
    )
    record_scores: list[RecordScore] = Field(
        default_factory=list, description="Per-record scoring detail"
    )
    scoring_cost: float = Field(default=0.0, ge=0, description="USD cost of scoring LLM calls")
    status: QualityStatus = Field(
        default=QualityStatus.PENDING, description="Scoring pipeline status"
    )
    error_message: str | None = Field(None, description="Error message if scoring failed")

    def to_table_item(self) -> dict[str, Any]:
        """Convert to high-level DynamoDB item format (for Table.put_item)."""
        item: dict[str, Any] = {
            "job_id": self.job_id,
            "scored_at": self.scored_at.isoformat(),
            "sample_size": self.sample_size,
            "total_records": self.total_records,
            "model_used_for_scoring": self.model_used_for_scoring,
            "aggregate_scores": {
                k: Decimal(str(v)) for k, v in self.aggregate_scores.items()
            },
            "diversity_score": Decimal(str(self.diversity_score)),
            "overall_score": Decimal(str(self.overall_score)),
            "record_scores": [rs.model_dump() for rs in self.record_scores],
            "scoring_cost": Decimal(str(self.scoring_cost)),
            "status": self.status.value,
        }
        if self.error_message is not None:
            item["error_message"] = self.error_message

        # Add TTL (90 days from now)
        ttl = int(datetime.now(UTC).timestamp() + (90 * 24 * 60 * 60))
        item["ttl"] = ttl

        return item

    @classmethod
    def from_dynamodb(cls, item: dict[str, Any]) -> "QualityMetrics":
        """Create QualityMetrics from DynamoDB table item."""
        aggregate_scores = {}
        for k, v in item.get("aggregate_scores", {}).items():
            aggregate_scores[k] = float(v)

        record_scores_raw = item.get("record_scores", [])
        record_scores = []
        for rs in record_scores_raw:
            record_scores.append(
                RecordScore(
                    record_index=int(rs["record_index"]),
                    coherence=float(rs["coherence"]),
                    relevance=float(rs["relevance"]),
                    format_compliance=float(rs["format_compliance"]),
                    detail=rs.get("detail", ""),
                )
            )

        return cls(
            job_id=item["job_id"],
            scored_at=datetime.fromisoformat(item["scored_at"]),
            sample_size=int(item["sample_size"]),
            total_records=int(item["total_records"]),
            model_used_for_scoring=item["model_used_for_scoring"],
            aggregate_scores=aggregate_scores,
            diversity_score=float(item.get("diversity_score", 0)),
            overall_score=float(item.get("overall_score", 0)),
            record_scores=record_scores,
            scoring_cost=float(item.get("scoring_cost", 0)),
            status=QualityStatus(item["status"]),
            error_message=item.get("error_message"),
        )
