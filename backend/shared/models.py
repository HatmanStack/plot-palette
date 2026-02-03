"""
Plot Palette - Pydantic Data Models

This module defines type-safe data models for jobs, templates, checkpoints,
and cost tracking using Pydantic for validation and serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from typing_extensions import NotRequired, TypedDict

from .constants import JobStatus


# TypedDict definitions for strongly-typed dictionaries
class TemplateStepDict(TypedDict):
    """Type definition for a template step configuration."""
    id: str
    prompt: str
    model: NotRequired[str]
    model_tier: NotRequired[str]


class TemplateDefinitionDict(TypedDict):
    """Type definition for a complete template definition."""
    steps: List[TemplateStepDict]


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
    partial_results: Dict[str, Any]
    step_outputs: Dict[str, str]


class JobConfig(BaseModel):
    """Job configuration and state model matching DynamoDB Jobs table schema."""

    job_id: str = Field(..., description="Unique job identifier (UUID)")
    user_id: str = Field(..., description="User who created the job")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Current job status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    config: Dict[str, Any] = Field(..., description="Job configuration dictionary (see JobConfigDict for structure)")
    budget_limit: float = Field(..., gt=0, description="Budget limit in USD")
    tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed")
    records_generated: int = Field(default=0, ge=0, description="Number of records generated")
    cost_estimate: float = Field(default=0.0, ge=0, description="Estimated cost in USD")

    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
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

    @staticmethod
    def _dict_to_dynamodb_map(d: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python dict to DynamoDB Map format."""
        result = {}
        for key, value in d.items():
            if isinstance(value, str):
                result[key] = {"S": value}
            elif isinstance(value, bool):  # Must check bool before int/float since bool is subclass of int
                result[key] = {"BOOL": value}
            elif isinstance(value, (int, float)):
                result[key] = {"N": str(value)}
            elif isinstance(value, dict):
                result[key] = {"M": JobConfig._dict_to_dynamodb_map(value)}
            elif isinstance(value, list):
                result[key] = {"L": [JobConfig._dict_to_dynamodb_map({"item": v})["item"] for v in value]}
        return result

    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> "JobConfig":
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
        )

    @staticmethod
    def _dynamodb_map_to_dict(m: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB Map to Python dict."""
        result = {}
        for key, value in m.items():
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                result[key] = float(value["N"])
            elif "BOOL" in value:
                result[key] = value["BOOL"]
            elif "M" in value:
                result[key] = JobConfig._dynamodb_map_to_dict(value["M"])
            elif "L" in value:
                result[key] = [JobConfig._dynamodb_map_to_dict({"item": v})["item"] for v in value["L"]]
        return result


class TemplateStep(BaseModel):
    """Single step in a multi-step template."""

    id: str = Field(..., description="Step identifier")
    model: Optional[str] = Field(None, description="Specific model ID to use")
    model_tier: Optional[str] = Field(None, description="Model tier (tier-1, tier-2, tier-3)")
    prompt: str = Field(..., description="Jinja2 prompt template")

    @field_validator("model_tier")
    @classmethod
    def validate_model_tier(cls, v):
        """Validate model tier if provided."""
        if v is not None and v not in ["tier-1", "tier-2", "tier-3", "cheap", "balanced", "premium"]:
            raise ValueError(f"Invalid model tier: {v}")
        return v


class TemplateDefinition(BaseModel):
    """Prompt template definition for generation jobs."""

    template_id: str = Field(..., description="Unique template identifier (UUID)")
    version: int = Field(default=1, ge=1, description="Template version number")
    name: str = Field(..., min_length=1, max_length=200, description="Template display name")
    user_id: str = Field(..., description="User who created the template")
    schema_requirements: List[str] = Field(
        default_factory=list,
        description="Required fields in seed data (e.g., ['author.biography', 'poem.text'])",
    )
    steps: List[TemplateStep] = Field(..., min_length=1, description="Generation steps")
    is_public: bool = Field(default=False, description="Whether template is shareable")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    def to_dynamodb(self) -> Dict[str, Any]:
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
    def from_dynamodb(cls, item: Dict[str, Any]) -> "TemplateDefinition":
        """Create TemplateDefinition from DynamoDB item."""
        # Parse the full template from the stored JSON
        template_data = cls.model_validate_json(item["steps"]["S"])
        # Override with DynamoDB-stored metadata
        template_data.template_id = item["template_id"]["S"]
        template_data.version = int(item["version"]["N"])
        template_data.name = item["name"]["S"]
        template_data.user_id = item["user_id"]["S"]
        template_data.schema_requirements = [req["S"] for req in item.get("schema_requirements", {}).get("L", [])]
        template_data.is_public = item.get("is_public", {}).get("BOOL", False)
        template_data.created_at = datetime.fromisoformat(item["created_at"]["S"])
        return template_data


class CheckpointState(BaseModel):
    """Checkpoint state for job recovery after spot interruptions."""

    job_id: str = Field(..., description="Job identifier")
    records_generated: int = Field(default=0, ge=0, description="Total records generated so far")
    current_batch: int = Field(default=0, ge=0, description="Current batch number")
    tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed")
    cost_accumulated: float = Field(default=0.0, ge=0, description="Cost accumulated in USD")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last checkpoint timestamp")
    resume_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom state for resuming generation (see ResumeStateDict for structure)",
    )
    etag: Optional[str] = Field(None, description="S3 ETag for concurrency control")

    def to_json(self) -> str:
        """Serialize to JSON for S3 storage."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str, etag: Optional[str] = None) -> "CheckpointState":
        """Deserialize from JSON."""
        checkpoint = cls.model_validate_json(json_str)
        checkpoint.etag = etag
        return checkpoint


class CostComponents(BaseModel):
    """Breakdown of costs by service."""

    bedrock: float = Field(default=0.0, ge=0, description="Bedrock API costs")
    fargate: float = Field(default=0.0, ge=0, description="Fargate compute costs")
    s3: float = Field(default=0.0, ge=0, description="S3 storage/operations costs")
    total: float = Field(default=0.0, ge=0, description="Total combined cost")


class CostBreakdown(BaseModel):
    """Cost breakdown for a specific time period."""

    job_id: str = Field(..., description="Job identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Measurement timestamp")
    bedrock_tokens: int = Field(default=0, ge=0, description="Tokens consumed by Bedrock")
    fargate_hours: float = Field(default=0.0, ge=0, description="Fargate compute hours")
    s3_operations: int = Field(default=0, ge=0, description="S3 API operation count")
    estimated_cost: CostComponents = Field(
        default_factory=CostComponents, description="Cost breakdown by service"
    )
    model_id: Optional[str] = Field(None, description="Model used for this period")

    def to_dynamodb(self) -> Dict[str, Any]:
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
        ttl = int((datetime.utcnow().timestamp() + (90 * 24 * 60 * 60)))
        item["ttl"] = {"N": str(ttl)}

        return item

    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> "CostBreakdown":
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


class QueueItem(BaseModel):
    """Queue item for job scheduling."""

    status: JobStatus = Field(..., description="Queue status (QUEUED, RUNNING, COMPLETED)")
    job_id: str = Field(..., description="Job identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Queue entry timestamp")
    priority: int = Field(default=0, description="Priority (higher = more urgent)")
    task_arn: Optional[str] = Field(None, description="ECS task ARN when running")

    @property
    def job_id_timestamp(self) -> str:
        """Composite sort key for DynamoDB."""
        return f"{self.job_id}#{self.timestamp.isoformat()}"

    def to_dynamodb(self) -> Dict[str, Any]:
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
    def from_dynamodb(cls, item: Dict[str, Any]) -> "QueueItem":
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
