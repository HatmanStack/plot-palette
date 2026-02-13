"""
Plot Palette - AWS Client Factory with Connection Pooling

This module provides singleton AWS clients with optimized connection pooling
and retry configuration for production workloads.
"""

import os
from functools import lru_cache
from typing import Optional

import boto3
from botocore.config import Config


def _get_endpoint_url() -> Optional[str]:
    """Return AWS_ENDPOINT_URL if set (for LocalStack), else None."""
    return os.environ.get("AWS_ENDPOINT_URL")


# Standard client configuration with connection pooling
_standard_config = Config(
    max_pool_connections=25,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=30,
)

# Extended timeout config for LLM calls (Bedrock)
_bedrock_config = Config(
    max_pool_connections=10,
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=120,  # LLM responses can take longer
)


@lru_cache(maxsize=1)
def get_dynamodb_resource(region_name: Optional[str] = None):
    """
    Get cached DynamoDB resource with connection pooling.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.resource: DynamoDB resource with optimized config
    """
    return boto3.resource(
        "dynamodb",
        config=_standard_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


@lru_cache(maxsize=1)
def get_dynamodb_client(region_name: Optional[str] = None):
    """
    Get cached DynamoDB client with connection pooling.

    Use this for TransactWriteItems and other low-level operations.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.client: DynamoDB client with optimized config
    """
    return boto3.client(
        "dynamodb",
        config=_standard_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


@lru_cache(maxsize=1)
def get_s3_client(region_name: Optional[str] = None):
    """
    Get cached S3 client with connection pooling.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.client: S3 client with optimized config
    """
    # S3 needs signature version for presigned URLs
    s3_config = Config(
        max_pool_connections=25,
        retries={"max_attempts": 3, "mode": "adaptive"},
        connect_timeout=5,
        read_timeout=30,
        signature_version="s3v4",
    )
    return boto3.client(
        "s3",
        config=s3_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


@lru_cache(maxsize=1)
def get_bedrock_client(region_name: Optional[str] = None):
    """
    Get cached Bedrock runtime client with extended timeouts.

    Bedrock LLM calls can take significant time, so this client
    is configured with 120-second read timeout.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.client: Bedrock runtime client with extended timeouts
    """
    return boto3.client(
        "bedrock-runtime",
        config=_bedrock_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


@lru_cache(maxsize=1)
def get_ecs_client(region_name: Optional[str] = None):
    """
    Get cached ECS client with connection pooling.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.client: ECS client with optimized config
    """
    return boto3.client(
        "ecs",
        config=_standard_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


@lru_cache(maxsize=1)
def get_sfn_client(region_name: Optional[str] = None):
    """
    Get cached Step Functions client with connection pooling.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.client: Step Functions client with optimized config
    """
    return boto3.client(
        "stepfunctions",
        config=_standard_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


@lru_cache(maxsize=1)
def get_sts_client(region_name: Optional[str] = None):
    """
    Get cached STS client for identity operations.

    Args:
        region_name: Optional AWS region override

    Returns:
        boto3.client: STS client
    """
    return boto3.client(
        "sts",
        config=_standard_config,
        region_name=region_name,
        endpoint_url=_get_endpoint_url(),
    )


def clear_client_cache():
    """
    Clear all cached clients.

    Useful for testing or when credentials need to be refreshed.
    """
    get_dynamodb_resource.cache_clear()
    get_dynamodb_client.cache_clear()
    get_s3_client.cache_clear()
    get_bedrock_client.cache_clear()
    get_ecs_client.cache_clear()
    get_sfn_client.cache_clear()
    get_sts_client.cache_clear()
