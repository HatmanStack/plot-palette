"""
Plot Palette - Utility Functions

This module provides utility functions for ID generation, cost calculation,
S3 operations, logging, and data manipulation.
"""

import logging
import os
import re
import sys
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .constants import (
    FARGATE_SPOT_PRICING,
    MODEL_PRICING,
    MODEL_TIERS,
    PRESIGNED_URL_EXPIRATION,
    S3_PRICING,
)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.

    Args:
        filename: Raw filename from user input

    Returns:
        str: Sanitized filename safe for S3 keys

    Raises:
        ValueError: If filename is empty or contains only invalid characters

    Examples:
        >>> sanitize_filename("../../../etc/passwd")
        'passwd'
        >>> sanitize_filename("my file (1).json")
        'my_file__1_.json'
        >>> sanitize_filename("data.json")
        'data.json'
    """
    # Extract basename to prevent path traversal
    basename = os.path.basename(filename)
    # Remove control characters
    basename = re.sub(r"[\x00-\x1f\x7f]", "", basename)
    # Replace unsafe characters with underscore, keeping only alphanumeric, dot, dash, underscore
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
    # Remove leading dots to prevent hidden files or relative paths
    sanitized = sanitized.lstrip(".")
    # Truncate to 255 characters (common filesystem limit)
    sanitized = sanitized[:255]

    if not sanitized:
        raise ValueError("Invalid filename")

    return sanitized


def sanitize_error_message(error: str, max_length: int = 200) -> str:
    """
    Sanitize error messages to prevent information leakage.

    Removes potentially sensitive information like file paths, stack traces,
    internal identifiers, and truncates to a safe length.

    Args:
        error: Raw error message
        max_length: Maximum length of output message

    Returns:
        str: Sanitized error message safe for client responses

    Examples:
        >>> sanitize_error_message("Error at /var/task/app.py:123")
        'Error occurred'
        >>> sanitize_error_message("KeyError: 'password'")
        'Invalid key error'
    """
    if not error:
        return "An error occurred"

    # Remove file paths
    sanitized = re.sub(r"(?:/[\w.-]+)+(?:\.\w+)?(?::\d+)?", "[path]", error)
    # Remove potential stack traces
    sanitized = re.sub(r"(?:File|Line|Traceback|at ).*", "", sanitized, flags=re.IGNORECASE)
    # Remove AWS resource identifiers (ARNs, account IDs)
    sanitized = re.sub(r"arn:aws:[a-zA-Z0-9-]+:[a-z0-9-]*:\d{12}:[^\s]+", "[resource]", sanitized)
    sanitized = re.sub(r"\b\d{12}\b", "[account]", sanitized)
    # Remove potential secrets/tokens (long alphanumeric strings)
    sanitized = re.sub(r"\b[A-Za-z0-9+/=]{32,}\b", "[redacted]", sanitized)
    # Clean up excessive whitespace
    sanitized = " ".join(sanitized.split())
    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[: max_length - 3] + "..."

    return sanitized.strip() or "An error occurred"


def estimate_tokens(text: str, model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0") -> int:
    """
    Estimate token count based on model family.

    Different model families have different tokenization characteristics.
    Claude models average ~3.5 characters per token, while Llama/Mistral
    average ~4 characters per token.

    Args:
        text: Input text to estimate tokens for
        model_id: Bedrock model identifier

    Returns:
        int: Estimated token count

    Examples:
        >>> estimate_tokens("Hello, world!", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        4
        >>> estimate_tokens("Hello, world!", "meta.llama3-1-8b-instruct-v1:0")
        3
    """
    if not text:
        return 0

    text_len = len(text)

    # Model-specific token estimation
    if "claude" in model_id.lower():
        # Claude: ~3.5 characters per token
        return max(1, int(text_len / 3.5))
    elif "llama" in model_id.lower() or "mistral" in model_id.lower():
        # Llama/Mistral: ~4 characters per token
        return max(1, int(text_len / 4))
    else:
        # Default: ~4 characters per token
        return max(1, int(text_len / 4))


def generate_job_id() -> str:
    """
    Generate a unique job identifier.

    Returns:
        str: UUID4 string in format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    """
    return str(uuid.uuid4())


def generate_template_id() -> str:
    """
    Generate a unique template identifier.

    Returns:
        str: UUID4 string
    """
    return str(uuid.uuid4())


def calculate_bedrock_cost(tokens: int, model_id: str, is_input: bool = True) -> float:
    """
    Calculate cost for Bedrock token usage.

    Args:
        tokens: Number of tokens consumed
        model_id: Bedrock model identifier
        is_input: True for input tokens, False for output tokens

    Returns:
        float: Cost in USD

    Raises:
        ValueError: If model_id is not recognized
    """
    if model_id not in MODEL_PRICING:
        raise ValueError(f"Unknown model ID: {model_id}")

    price_per_million = MODEL_PRICING[model_id]["input" if is_input else "output"]
    return (tokens / 1_000_000) * price_per_million


def calculate_fargate_cost(vcpu: float, memory_gb: float, hours: float) -> float:
    """
    Calculate cost for Fargate Spot usage.

    Args:
        vcpu: Number of vCPUs
        memory_gb: Memory in GB
        hours: Runtime in hours

    Returns:
        float: Cost in USD
    """
    vcpu_cost = vcpu * FARGATE_SPOT_PRICING["vcpu"] * hours
    memory_cost = memory_gb * FARGATE_SPOT_PRICING["memory"] * hours
    return vcpu_cost + memory_cost


def calculate_s3_cost(puts: int = 0, gets: int = 0) -> float:
    """
    Calculate cost for S3 API operations.

    Args:
        puts: Number of PUT/POST/COPY requests
        gets: Number of GET requests

    Returns:
        float: Cost in USD
    """
    put_cost = puts * S3_PRICING["PUT"]
    get_cost = gets * S3_PRICING["GET"]
    return put_cost + get_cost


def get_nested_field(data: dict[str, Any], field_path: str) -> Any:
    """
    Get value from nested dictionary using dot notation.

    Args:
        data: Dictionary to search
        field_path: Path in dot notation (e.g., "author.biography")

    Returns:
        Any: Value at the specified path, or None if not found

    Examples:
        >>> data = {"author": {"biography": "Born in..."}}
        >>> get_nested_field(data, "author.biography")
        'Born in...'
    """
    keys = field_path.split(".")
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current


def set_nested_field(data: dict[str, Any], field_path: str, value: Any) -> None:
    """
    Set value in nested dictionary using dot notation.

    Args:
        data: Dictionary to modify (modified in-place)
        field_path: Path in dot notation
        value: Value to set

    Examples:
        >>> data = {}
        >>> set_nested_field(data, "author.name", "Jane Doe")
        >>> data
        {'author': {'name': 'Jane Doe'}}
    """
    keys = field_path.split(".")
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


def create_presigned_url(
    bucket: str,
    key: str,
    expiration: int = PRESIGNED_URL_EXPIRATION,
    method: str = "get_object",
) -> str:
    """
    Generate a presigned URL for S3 object access.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        expiration: URL expiration time in seconds
        method: S3 operation (get_object, put_object)

    Returns:
        str: Presigned URL

    Raises:
        ClientError: If URL generation fails
    """
    from .aws_clients import get_s3_client

    s3_client = get_s3_client()

    try:
        url = s3_client.generate_presigned_url(
            method,
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logging.error(f"Error generating presigned URL: {e}")
        raise


def parse_etag(etag: str) -> str:
    """
    Clean S3 ETag string by removing quotes.

    Args:
        etag: Raw ETag from S3 (may include quotes)

    Returns:
        str: Cleaned ETag

    Examples:
        >>> parse_etag('"abc123"')
        'abc123'
    """
    return etag.strip('"')


def resolve_model_id(model_id_or_tier: str) -> str:
    """
    Resolve model tier alias to actual model ID.

    Args:
        model_id_or_tier: Either a model ID or tier alias (tier-1, cheap, etc.)

    Returns:
        str: Actual Bedrock model ID

    Examples:
        >>> resolve_model_id("tier-1")
        'meta.llama3-1-8b-instruct-v1:0'
        >>> resolve_model_id("anthropic.claude-3-5-sonnet-20241022-v2:0")
        'anthropic.claude-3-5-sonnet-20241022-v2:0'
    """
    if model_id_or_tier in MODEL_TIERS:
        return MODEL_TIERS[model_id_or_tier]
    return model_id_or_tier


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configure structured JSON logger for CloudWatch Logs.

    Args:
        name: Logger name (typically __name__)
        level: Logging level

    Returns:
        logging.Logger: Configured logger instance

    Examples:
        >>> logger = setup_logger(__name__)
        >>> logger.info(json.dumps({"event": "job_started", "job_id": "123"}))
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create formatter (JSON for structured logging)
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)s}'
    )
    handler.setFormatter(formatter)

    # Add handler to logger
    if not logger.handlers:
        logger.addHandler(handler)

    return logger


def extract_schema_requirements(template_definition: dict[str, Any]) -> list[str]:
    """
    Extract all {{ variable }} references from a Jinja2 template definition.

    Args:
        template_definition: Template definition dictionary with steps

    Returns:
        Sorted list of unique variable references

    Raises:
        ValueError: If template syntax is invalid
    """
    import jinja2

    env = jinja2.Environment(autoescape=True)
    all_variables: set[str] = set()

    try:
        for step in template_definition.get("steps", []):
            prompt = step.get("prompt", "")
            parsed_template = env.parse(prompt)
            variables = jinja2.meta.find_undeclared_variables(parsed_template)
            all_variables.update(variables)

        built_ins = {"steps", "loop", "range", "dict", "list"}
        schema_vars = [v for v in all_variables if v not in built_ins]

        return sorted(schema_vars)

    except jinja2.TemplateSyntaxError as e:
        raise ValueError(f"Invalid template syntax: {str(e)}") from e


def validate_seed_data(data: dict[str, Any], required_fields: list[str]) -> tuple[bool, str | None]:
    """
    Validate that seed data contains all required fields.

    Args:
        data: Seed data dictionary
        required_fields: List of required field paths (dot notation)

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)

    Examples:
        >>> data = {"author": {"name": "Jane"}}
        >>> validate_seed_data(data, ["author.name", "author.bio"])
        (False, "Missing required field: author.bio")
    """
    for field in required_fields:
        value = get_nested_field(data, field)
        if value is None:
            return False, f"Missing required field: {field}"

    return True, None


def format_cost(cost: float) -> str:
    """
    Format cost as USD string.

    Args:
        cost: Cost in USD

    Returns:
        str: Formatted cost string

    Examples:
        >>> format_cost(12.5)
        '$12.50'
        >>> format_cost(0.003)
        '$0.00'
    """
    return f"${cost:.2f}"


def format_timestamp(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 string.

    Args:
        dt: Datetime object

    Returns:
        str: ISO 8601 formatted string

    Examples:
        >>> format_timestamp(datetime(2025, 11, 19, 10, 30, 0))
        '2025-11-19T10:30:00'
    """
    return dt.isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp string.

    Args:
        timestamp_str: ISO 8601 formatted string

    Returns:
        datetime: Parsed datetime object

    Examples:
        >>> parse_timestamp('2025-11-19T10:30:00')
        datetime.datetime(2025, 11, 19, 10, 30, 0)
    """
    return datetime.fromisoformat(timestamp_str)


@lru_cache(maxsize=128)
def get_aws_account_id() -> str:
    """
    Get AWS account ID (cached).

    Returns:
        str: AWS account ID

    Raises:
        ClientError: If unable to retrieve account ID
    """
    from .aws_clients import get_sts_client

    sts_client = get_sts_client()
    return sts_client.get_caller_identity()["Account"]


@lru_cache(maxsize=128)
def get_aws_region() -> str:
    """
    Get current AWS region (cached).

    Returns:
        str: AWS region name
    """
    session = boto3.session.Session()
    return session.region_name or "us-east-1"
