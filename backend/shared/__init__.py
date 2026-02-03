"""
Plot Palette - Backend Shared Library

This package provides shared models, constants, and utilities used across
Lambda functions and ECS tasks.
"""

from .aws_clients import (
    clear_client_cache,
    get_bedrock_client,
    get_dynamodb_client,
    get_dynamodb_resource,
    get_ecs_client,
    get_s3_client,
    get_sts_client,
)
from .constants import (
    CHECKPOINT_INTERVAL,
    DEFAULT_BUDGET_LIMIT,
    EXPORT_FILE_NAMES,
    FARGATE_SPOT_PRICING,
    FARGATE_TASK_SIZES,
    GSI_NAMES,
    MAX_CONCURRENT_JOBS,
    MAX_RETRIES,
    MODEL_PRICING,
    MODEL_TIERS,
    RETRY_BACKOFF_BASE,
    S3_FOLDERS,
    S3_PRICING,
    TABLE_NAMES,
    ExportFormat,
    JobStatus,
)
from .models import (
    CheckpointState,
    CostBreakdown,
    CostComponents,
    JobConfig,
    # TypedDict definitions
    JobConfigDict,
    QueueItem,
    ResumeStateDict,
    TemplateDefinition,
    TemplateDefinitionDict,
    TemplateStep,
    TemplateStepDict,
)
from .retry import (
    CircuitBreaker,
    CircuitBreakerOpen,
    get_circuit_breaker,
    is_retryable_error,
    retry_with_backoff,
)
from .utils import (
    calculate_bedrock_cost,
    calculate_fargate_cost,
    calculate_s3_cost,
    create_presigned_url,
    estimate_tokens,
    format_cost,
    format_timestamp,
    generate_job_id,
    generate_template_id,
    get_aws_account_id,
    get_aws_region,
    get_nested_field,
    parse_etag,
    parse_timestamp,
    resolve_model_id,
    sanitize_error_message,
    # New security utilities
    sanitize_filename,
    set_nested_field,
    setup_logger,
    validate_seed_data,
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
