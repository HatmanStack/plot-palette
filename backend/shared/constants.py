"""
Plot Palette - Application Constants

This module defines all application-wide constants including pricing,
configuration values, and enumeration types.
"""

from enum import StrEnum


# Job Status Values
class JobStatus(StrEnum):
    """Job status enumeration."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CANCELLED = "CANCELLED"


# Export Format Types
class ExportFormat(StrEnum):
    """Dataset export format enumeration."""

    JSONL = "JSONL"
    PARQUET = "PARQUET"
    CSV = "CSV"


# AWS Bedrock Model Pricing (per 1M tokens)
# Source: https://aws.amazon.com/bedrock/pricing/ (as of 2025-01)
MODEL_PRICING = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {
        "input": 3.00,
        "output": 15.00,
        "name": "Claude 3.5 Sonnet",
    },
    "meta.llama3-1-70b-instruct-v1:0": {
        "input": 0.99,
        "output": 0.99,
        "name": "Llama 3.1 70B",
    },
    "meta.llama3-1-8b-instruct-v1:0": {
        "input": 0.30,
        "output": 0.60,
        "name": "Llama 3.1 8B",
    },
    "mistral.mistral-7b-instruct-v0:2": {
        "input": 0.15,
        "output": 0.20,
        "name": "Mistral 7B",
    },
}

# Model Tier Aliases for Smart Routing
MODEL_TIERS = {
    "tier-1": "meta.llama3-1-8b-instruct-v1:0",  # Cheap - simple transformations
    "tier-2": "meta.llama3-1-70b-instruct-v1:0",  # Balanced - moderate complexity
    "tier-3": "anthropic.claude-3-5-sonnet-20241022-v2:0",  # Premium - complex reasoning
    "cheap": "meta.llama3-1-8b-instruct-v1:0",
    "balanced": "meta.llama3-1-70b-instruct-v1:0",
    "premium": "anthropic.claude-3-5-sonnet-20241022-v2:0",
}

# AWS Fargate Spot Pricing (per hour)
# Source: https://aws.amazon.com/fargate/pricing/ (Spot pricing, us-east-1)
FARGATE_SPOT_PRICING = {
    "vcpu": 0.01246,  # per vCPU hour
    "memory": 0.00127,  # per GB hour
}

# Typical ECS task sizes
FARGATE_TASK_SIZES = {
    "small": {"vcpu": 0.25, "memory": 0.5},  # 0.25 vCPU, 0.5 GB
    "medium": {"vcpu": 0.5, "memory": 1.0},  # 0.5 vCPU, 1 GB
    "large": {"vcpu": 1.0, "memory": 2.0},  # 1 vCPU, 2 GB
    "xlarge": {"vcpu": 2.0, "memory": 4.0},  # 2 vCPU, 4 GB
}

# S3 Pricing (per request)
# Source: https://aws.amazon.com/s3/pricing/ (us-east-1)
S3_PRICING = {
    "PUT": 0.005 / 1000,  # $0.005 per 1000 PUT requests
    "GET": 0.0004 / 1000,  # $0.0004 per 1000 GET requests
    "DELETE": 0.0,  # Free
}

# DynamoDB Pricing (on-demand, per 1M requests)
# Source: https://aws.amazon.com/dynamodb/pricing/ (us-east-1)
DYNAMODB_PRICING = {
    "write": 1.25,  # $1.25 per million write request units
    "read": 0.25,  # $0.25 per million read request units
}

# Checkpoint Configuration
CHECKPOINT_INTERVAL = 50  # Save checkpoint every N records generated
CHECKPOINT_BUCKET_PREFIX = "jobs/"  # S3 prefix for checkpoints

# Budget Configuration
BUDGET_CHECK_INTERVAL = 1  # Check budget before every Bedrock API call
DEFAULT_BUDGET_LIMIT = 100.0  # Default budget limit in USD

# Data Lifecycle Configuration
GLACIER_ARCHIVE_DAYS = 3  # Days before archiving job outputs to Glacier
SEED_DATA_INTELLIGENT_TIERING_DAYS = 30  # Days before moving seed data to Intelligent Tiering
COST_TRACKING_TTL_DAYS = 90  # Days to retain cost tracking records

# Concurrency Configuration
MAX_CONCURRENT_JOBS = 5  # Maximum number of concurrent generation jobs
MAX_RETRIES = 3  # Maximum retries for Bedrock API calls
RETRY_BACKOFF_BASE = 2  # Exponential backoff base (seconds)

# Presigned URL Configuration
PRESIGNED_URL_EXPIRATION = 900  # Presigned URL expiration time (15 minutes)

# Template Engine Configuration
MAX_TEMPLATE_STEPS = 10  # Maximum number of steps in a multi-step template
MAX_TEMPLATE_SIZE = 50000  # Maximum template size in characters

# CloudWatch Logs Configuration
LOG_GROUP_PREFIX = "/aws/ecs/plot-palette"
LOG_RETENTION_DAYS = 30  # Days to retain CloudWatch logs

# API Configuration
API_THROTTLE_RATE = 1000  # Requests per second per user
API_THROTTLE_BURST = 2000  # Burst capacity

# Cognito Configuration
PASSWORD_MIN_LENGTH = 12
TOKEN_EXPIRATION_HOURS = 1  # Access token expiration
REFRESH_TOKEN_EXPIRATION_DAYS = 30  # Refresh token expiration

# DynamoDB Table Names (will be prefixed with environment)
TABLE_NAMES = {
    "jobs": "Jobs",
    "queue": "Queue",
    "templates": "Templates",
    "cost_tracking": "CostTracking",
}

# DynamoDB GSI Names
GSI_NAMES = {
    "user_id_index": "user-id-index",
}

# S3 Folder Structure
S3_FOLDERS = {
    "seed_data": "seed-data/",
    "sample_datasets": "sample-datasets/",
    "jobs": "jobs/",
    "checkpoints": "jobs/{job_id}/",
    "outputs": "jobs/{job_id}/outputs/",
    "exports": "jobs/{job_id}/exports/",
}

# Export File Names
EXPORT_FILE_NAMES = {
    "jsonl": "dataset.jsonl",
    "parquet": "dataset.parquet",
    "csv": "dataset.csv",
}

# Worker Exit Codes (used by Step Functions to determine terminal status)
WORKER_EXIT_SUCCESS = 0
WORKER_EXIT_ERROR = 1
WORKER_EXIT_BUDGET_EXCEEDED = 2

# Spot Interruption Signal
SPOT_INTERRUPTION_SIGNAL = 15  # SIGTERM (120 seconds before termination)

# Default AWS Region
DEFAULT_AWS_REGION = "us-east-1"
