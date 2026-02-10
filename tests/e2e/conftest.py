"""
E2E test fixtures using LocalStack.

Sets up real DynamoDB tables and S3 buckets via LocalStack,
then configures Lambda handlers to use them.
"""

import json
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend shared modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

ENDPOINT_URL = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
USER_ID = 'e2e-test-user-001'


@pytest.fixture(scope='session', autouse=True)
def localstack_resources():
    """Provision LocalStack resources once per test session."""
    from tests.e2e.localstack_setup import create_buckets, create_tables

    tables = create_tables(ENDPOINT_URL)
    bucket = create_buckets(ENDPOINT_URL)

    # Set env vars that Lambda handlers read at module import time
    env = {
        'AWS_ENDPOINT_URL': ENDPOINT_URL,
        'AWS_DEFAULT_REGION': 'us-east-1',
        'AWS_REGION': 'us-east-1',
        'AWS_ACCESS_KEY_ID': 'testing',
        'AWS_SECRET_ACCESS_KEY': 'testing',
        'JOBS_TABLE_NAME': tables['jobs'],
        'QUEUE_TABLE_NAME': tables['queue'],
        'TEMPLATES_TABLE_NAME': tables['templates'],
        'COST_TRACKING_TABLE_NAME': tables['cost_tracking'],
        'BUCKET_NAME': bucket,
        # ECS config (mocked - LocalStack free doesn't support ECS)
        'ECS_CLUSTER_NAME': 'e2e-cluster',
        'TASK_DEFINITION_ARN': 'e2e-task-def',
        'SUBNET_IDS': 'subnet-e2e001',
        'SECURITY_GROUP_ID': 'sg-e2e001',
    }
    for k, v in env.items():
        os.environ[k] = v

    # Clear the aws_clients cache so new clients use LocalStack endpoint
    from shared.aws_clients import clear_client_cache
    clear_client_cache()

    yield {'tables': tables, 'bucket': bucket}

    # Cleanup: clear cache after session
    clear_client_cache()


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """Clear cached boto3 clients around each test."""
    from shared.aws_clients import clear_client_cache
    clear_client_cache()
    yield
    clear_client_cache()


@pytest.fixture(autouse=True)
def mock_ecs():
    """Mock ECS client since LocalStack free doesn't support ECS."""
    mock = MagicMock()
    mock.run_task.return_value = {
        'tasks': [{
            'taskArn': 'arn:aws:ecs:us-east-1:000000000000:task/e2e-cluster/mock-task',
            'lastStatus': 'PENDING',
        }],
        'failures': [],
    }
    mock.stop_task.return_value = {}
    with patch('shared.aws_clients.get_ecs_client', return_value=mock):
        yield mock


@pytest.fixture(autouse=True)
def mock_bedrock():
    """Mock Bedrock client for template test endpoint."""
    mock = MagicMock()

    def mock_invoke(**kwargs):
        return {
            'body': MagicMock(
                read=lambda: json.dumps({
                    'content': [{'text': 'Mock E2E response'}],
                    'usage': {'input_tokens': 10, 'output_tokens': 5},
                }).encode()
            )
        }

    mock.invoke_model.side_effect = mock_invoke
    with patch('shared.aws_clients.get_bedrock_client', return_value=mock):
        yield mock


def make_api_event(
    method: str,
    path: str,
    body: Any = None,
    user_id: str = USER_ID,
    path_parameters: dict | None = None,
    query_parameters: dict | None = None,
) -> dict:
    """Build an API Gateway v2 event dict for Lambda handler invocation."""
    event: dict[str, Any] = {
        'requestContext': {
            'http': {'method': method, 'path': path},
            'authorizer': {
                'jwt': {
                    'claims': {
                        'sub': user_id,
                        'email': f'{user_id}@example.com',
                    }
                }
            },
        },
        'headers': {'content-type': 'application/json'},
        'pathParameters': path_parameters or {},
        'queryStringParameters': query_parameters,
    }
    if body is not None:
        event['body'] = json.dumps(body) if not isinstance(body, str) else body
    return event
