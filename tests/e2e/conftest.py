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

# ---------------------------------------------------------------------------
# Import shim for Lambda handlers
# ---------------------------------------------------------------------------
# Lambda handlers do:
#   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))
#   from utils import ...           # bare import
#   from aws_clients import ...     # bare import
#
# The shared modules themselves use relative imports (from .constants import ...).
# Relative imports only work when modules are loaded as part of a package.
#
# Strategy: import every shared module as part of the `shared` package first
# (which resolves relative imports correctly), then register each module under
# its *bare* name in sys.modules so Lambda handler `from utils import ...` works.
# ---------------------------------------------------------------------------
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Import shared as a proper package (resolves relative imports)
import shared  # noqa: E402
import shared.aws_clients  # noqa: E402
import shared.constants  # noqa: E402
import shared.lambda_responses  # noqa: E402
import shared.models  # noqa: E402
import shared.retry  # noqa: E402
import shared.template_filters  # noqa: E402
import shared.utils  # noqa: E402

# Alias bare names so `from utils import ...` in Lambda handlers works
for _mod_name in [
    'aws_clients', 'constants', 'lambda_responses', 'models',
    'retry', 'template_filters', 'utils',
]:
    sys.modules[_mod_name] = getattr(shared, _mod_name)

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
        # Step Functions config (mocked)
        'STATE_MACHINE_ARN': 'arn:aws:states:us-east-1:000000000000:stateMachine:plot-palette-job-lifecycle-e2e',
    }
    for k, v in env.items():
        os.environ[k] = v

    # Clear the aws_clients cache so new clients use LocalStack endpoint
    shared.aws_clients.clear_client_cache()

    yield {'tables': tables, 'bucket': bucket}

    shared.aws_clients.clear_client_cache()


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """Clear cached boto3 clients around each test."""
    shared.aws_clients.clear_client_cache()
    yield
    shared.aws_clients.clear_client_cache()


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
def mock_sfn():
    """Mock Step Functions client since LocalStack free doesn't support SFN."""
    mock = MagicMock()
    mock.start_execution.return_value = {
        'executionArn': 'arn:aws:states:us-east-1:000000000000:execution:plot-palette-job-lifecycle-e2e:mock-exec',
        'startDate': '2025-01-01T00:00:00Z',
    }
    mock.stop_execution.return_value = {}
    with patch('shared.aws_clients.get_sfn_client', return_value=mock):
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
