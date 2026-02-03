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
    CostComponents,
    QueueItem,
    # TypedDict definitions
    JobConfigDict,
    TemplateStepDict,
    TemplateDefinitionDict,
    ResumeStateDict,
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
    # New security utilities
    sanitize_filename,
    sanitize_error_message,
    estimate_tokens,
)
from .aws_clients import (
    get_dynamodb_resource,
    get_dynamodb_client,
    get_s3_client,
    get_bedrock_client,
    get_ecs_client,
    get_sts_client,
    clear_client_cache,
)
from .retry import (
    retry_with_backoff,
    CircuitBreaker,
    CircuitBreakerOpen,
    get_circuit_breaker,
    is_retryable_error,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "JobConfig",
    "TemplateDefinition",
    "TemplateStep",
    "CheckpointState",
    "CostBreakdown",
    "CostComponents",
    "QueueItem",
    # TypedDict definitions
    "JobConfigDict",
    "TemplateStepDict",
    "TemplateDefinitionDict",
    "ResumeStateDict",
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
    "sanitize_filename",
    "sanitize_error_message",
    "estimate_tokens",
    # AWS Clients
    "get_dynamodb_resource",
    "get_dynamodb_client",
    "get_s3_client",
    "get_bedrock_client",
    "get_ecs_client",
    "get_sts_client",
    "clear_client_cache",
    # Retry utilities
    "retry_with_backoff",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "get_circuit_breaker",
    "is_retryable_error",
]
