"""
Plot Palette - Integration Test Fixtures

Pytest fixtures for integration testing of API endpoints.
"""

import pytest
import boto3
import os
import json
from datetime import datetime
from typing import Dict, Any


@pytest.fixture(scope="session")
def api_endpoint():
    """Get API endpoint from environment variable."""
    endpoint = os.getenv('API_ENDPOINT')
    if not endpoint:
        pytest.skip("API_ENDPOINT environment variable not set")
    return endpoint


@pytest.fixture(scope="session")
def cognito_client():
    """Create Cognito client."""
    return boto3.client('cognito-idp')


@pytest.fixture(scope="session")
def cognito_config():
    """Get Cognito configuration from environment."""
    user_pool_id = os.getenv('USER_POOL_ID')
    client_id = os.getenv('CLIENT_ID')

    if not user_pool_id or not client_id:
        pytest.skip("USER_POOL_ID and CLIENT_ID environment variables required")

    return {
        'user_pool_id': user_pool_id,
        'client_id': client_id
    }


@pytest.fixture(scope="session")
def test_user(cognito_client, cognito_config):
    """Create a test user and return credentials."""
    # Generate unique email for this test run
    timestamp = datetime.now().timestamp()
    test_email = f"test+{int(timestamp)}@plotpalette.test"
    test_password = "TestPassword123!@#"

    user_pool_id = cognito_config['user_pool_id']
    client_id = cognito_config['client_id']

    # Create test user
    try:
        cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=test_email,
            TemporaryPassword=test_password,
            MessageAction='SUPPRESS',
            UserAttributes=[
                {'Name': 'email', 'Value': test_email},
                {'Name': 'email_verified', 'Value': 'true'}
            ]
        )

        # Set permanent password
        cognito_client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=test_email,
            Password=test_password,
            Permanent=True
        )

    except cognito_client.exceptions.UsernameExistsException:
        # User already exists, continue
        pass

    yield {
        'email': test_email,
        'password': test_password,
        'user_pool_id': user_pool_id,
        'client_id': client_id
    }

    # Cleanup - delete test user
    try:
        cognito_client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=test_email
        )
    except:
        pass  # Best effort cleanup


@pytest.fixture(scope="session")
def auth_token(cognito_client, test_user):
    """Get authentication token for test user."""
    try:
        response = cognito_client.initiate_auth(
            ClientId=test_user['client_id'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': test_user['email'],
                'PASSWORD': test_user['password']
            }
        )

        return response['AuthenticationResult']['IdToken']

    except Exception as e:
        pytest.fail(f"Failed to authenticate test user: {str(e)}")


@pytest.fixture
def auth_headers(auth_token):
    """Generate authorization headers."""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture(scope="session")
def dynamodb_client():
    """Create DynamoDB client."""
    return boto3.client('dynamodb')


@pytest.fixture(scope="session")
def s3_client():
    """Create S3 client."""
    return boto3.client('s3')


@pytest.fixture
def sample_template_definition() -> Dict[str, Any]:
    """Sample template definition for testing."""
    return {
        "steps": [
            {
                "id": "question",
                "model": "meta.llama3-1-8b-instruct-v1:0",
                "prompt": "Generate a question about {{ author.name }} based on their work."
            },
            {
                "id": "answer",
                "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "prompt": "Answer this question using context from {{ poem.text }}: {{ steps.question.output }}"
            }
        ]
    }


@pytest.fixture
def sample_seed_data() -> Dict[str, Any]:
    """Sample seed data for testing."""
    return {
        "author": {
            "name": "Emily Dickinson",
            "biography": "American poet known for unconventional style"
        },
        "poem": {
            "title": "Hope is the thing with feathers",
            "text": "Hope is the thing with feathers that perches in the soul..."
        }
    }


@pytest.fixture
def sample_job_config(sample_template_definition) -> Dict[str, Any]:
    """Sample job configuration for testing."""
    return {
        "template_id": "test-template-id",  # Will be replaced with actual template ID
        "seed_data_path": "seed-data/test/sample.json",
        "budget_limit": 50.0,
        "output_format": "JSONL",
        "num_records": 100
    }
