"""
Plot Palette - Backend Shared Library

This package provides shared models, constants, and utilities used across
Lambda functions and ECS tasks.
"""

from .models import (
    JobConfig,
    TemplateDefinition,
    TemplateStep,
    CheckpointState,
    CostBreakdown,
    QueueItem,
)
from .constants import (
    JobStatus,
    ExportFormat,
    MODEL_PRICING,
    MODEL_TIERS,
    FARGATE_SPOT_PRICING,
    FARGATE_TASK_SIZES,
    S3_PRICING,
    CHECKPOINT_INTERVAL,
    DEFAULT_BUDGET_LIMIT,
    MAX_CONCURRENT_JOBS,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    TABLE_NAMES,
    GSI_NAMES,
    S3_FOLDERS,
    EXPORT_FILE_NAMES,
)
from .utils import (
    generate_job_id,
    generate_template_id,
    calculate_bedrock_cost,
    calculate_fargate_cost,
    calculate_s3_cost,
    get_nested_field,
    set_nested_field,
    create_presigned_url,
    parse_etag,
    resolve_model_id,
    setup_logger,
    validate_seed_data,
    format_cost,
    format_timestamp,
    parse_timestamp,
    get_aws_account_id,
    get_aws_region,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "JobConfig",
    "TemplateDefinition",
    "TemplateStep",
    "CheckpointState",
    "CostBreakdown",
    "QueueItem",
    # Constants
    "JobStatus",
    "ExportFormat",
    "MODEL_PRICING",
    "MODEL_TIERS",
    "FARGATE_SPOT_PRICING",
    "FARGATE_TASK_SIZES",
    "S3_PRICING",
    "CHECKPOINT_INTERVAL",
    "DEFAULT_BUDGET_LIMIT",
    "MAX_CONCURRENT_JOBS",
    "MAX_RETRIES",
    "RETRY_BACKOFF_BASE",
    "TABLE_NAMES",
    "GSI_NAMES",
    "S3_FOLDERS",
    "EXPORT_FILE_NAMES",
    # Utilities
    "generate_job_id",
    "generate_template_id",
    "calculate_bedrock_cost",
    "calculate_fargate_cost",
    "calculate_s3_cost",
    "get_nested_field",
    "set_nested_field",
    "create_presigned_url",
    "parse_etag",
    "resolve_model_id",
    "setup_logger",
    "validate_seed_data",
    "format_cost",
    "format_timestamp",
    "parse_timestamp",
    "get_aws_account_id",
    "get_aws_region",
]
