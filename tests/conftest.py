"""
Plot Palette - Root Test Fixtures

Shared pytest fixtures for all tests. Provides mock AWS clients,
environment variables, and common test data.
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from datetime import datetime
from typing import Dict, Any, Generator

# Set up test environment variables before any imports
@pytest.fixture(scope="session", autouse=True)
def test_environment() -> Generator[None, None, None]:
    """Set up test environment variables."""
    env_vars = {
        "AWS_REGION": "us-east-1",
        "JOBS_TABLE": "test-jobs-table",
        "TEMPLATES_TABLE": "test-templates-table",
        "QUEUE_TABLE": "test-queue-table",
        "CHECKPOINTS_BUCKET": "test-checkpoints-bucket",
        "OUTPUT_BUCKET": "test-output-bucket",
        "SEED_DATA_BUCKET": "test-seed-data-bucket",
        "USER_POOL_ID": "us-east-1_test123",
        "CLIENT_ID": "test-client-id",
        "ECS_CLUSTER": "test-cluster",
        "TASK_DEFINITION": "test-task-def",
        "SUBNET_ID": "subnet-test123",
        "SECURITY_GROUP_ID": "sg-test123",
        "STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:plot-palette-job-lifecycle-test",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }

    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def mock_dynamodb_client() -> MagicMock:
    """Create a mock DynamoDB client."""
    client = MagicMock()

    # Default behaviors
    client.get_item.return_value = {"Item": None}
    client.put_item.return_value = {}
    client.update_item.return_value = {}
    client.delete_item.return_value = {}
    client.query.return_value = {"Items": [], "Count": 0}
    client.scan.return_value = {"Items": [], "Count": 0}

    return client


@pytest.fixture
def mock_s3_client() -> MagicMock:
    """Create a mock S3 client."""
    client = MagicMock()

    # Default behaviors
    client.get_object.return_value = {
        "Body": MagicMock(read=lambda: b'{"test": "data"}'),
        "ETag": '"test-etag-123"',
    }
    client.put_object.return_value = {"ETag": '"new-etag-456"'}
    client.head_object.return_value = {"ContentLength": 1024}
    client.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/key?signature=abc"

    return client


@pytest.fixture
def mock_bedrock_client() -> MagicMock:
    """Create a mock Bedrock runtime client."""
    import json

    client = MagicMock()

    # Mock Claude response
    def mock_invoke(*args, **kwargs):
        model_id = kwargs.get("modelId", "")

        if "claude" in model_id.lower():
            response_body = {
                "content": [{"text": "Mock Claude response"}],
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }
        elif "llama" in model_id.lower():
            response_body = {
                "generation": "Mock Llama response",
                "prompt_token_count": 100,
                "generation_token_count": 50
            }
        elif "mistral" in model_id.lower():
            response_body = {
                "outputs": [{"text": "Mock Mistral response"}],
            }
        else:
            response_body = {"output": "Mock response"}

        return {
            "body": MagicMock(read=lambda: json.dumps(response_body).encode())
        }

    client.invoke_model.side_effect = mock_invoke

    return client


@pytest.fixture
def mock_cognito_client() -> MagicMock:
    """Create a mock Cognito client."""
    client = MagicMock()

    client.get_user.return_value = {
        "Username": "test-user-id",
        "UserAttributes": [
            {"Name": "email", "Value": "test@example.com"},
            {"Name": "sub", "Value": "test-user-id"},
        ]
    }

    return client


@pytest.fixture
def mock_ecs_client() -> MagicMock:
    """Create a mock ECS client."""
    client = MagicMock()

    client.run_task.return_value = {
        "tasks": [
            {
                "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/abc123",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
                "lastStatus": "PENDING",
            }
        ],
        "failures": []
    }
    client.stop_task.return_value = {}
    client.describe_tasks.return_value = {
        "tasks": [{"lastStatus": "RUNNING", "taskArn": "arn:aws:ecs:test"}]
    }

    return client


@pytest.fixture
def mock_sfn_client() -> MagicMock:
    """Create a mock Step Functions client."""
    client = MagicMock()

    client.start_execution.return_value = {
        "executionArn": "arn:aws:states:us-east-1:123456789012:execution:plot-palette-job-lifecycle:job-test-123",
        "startDate": datetime.utcnow(),
    }
    client.stop_execution.return_value = {}
    client.describe_execution.return_value = {
        "executionArn": "arn:aws:states:us-east-1:123456789012:execution:plot-palette-job-lifecycle:job-test-123",
        "status": "RUNNING",
    }

    return client


@pytest.fixture
def sample_user() -> Dict[str, Any]:
    """Sample user data for testing."""
    return {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "sub": "test-user-123",
    }


@pytest.fixture
def sample_jwt_claims(sample_user) -> Dict[str, Any]:
    """Sample JWT claims for testing authenticated requests."""
    return {
        "sub": sample_user["user_id"],
        "email": sample_user["email"],
        "email_verified": True,
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_test123",
        "cognito:username": sample_user["user_id"],
        "aud": "test-client-id",
        "token_use": "id",
        "auth_time": int(datetime.utcnow().timestamp()),
        "exp": int(datetime.utcnow().timestamp()) + 3600,
    }
