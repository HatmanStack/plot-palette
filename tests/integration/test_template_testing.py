"""
Plot Palette - Integration Tests for Template Testing Endpoint

Tests the POST /templates/{template_id}/test endpoint for dry-run template execution.
Requires deployed AWS infrastructure and test_helpers module.
"""

import pytest

pytest.skip("Requires deployed AWS infrastructure", allow_module_level=True)


@pytest.fixture(scope="module")
def test_user():
    """Create a test user for the test session."""
    user = create_test_user()
    yield user
    cleanup_test_user(user)


@pytest.fixture(scope="module")
def auth_token(test_user):
    """Get authentication token for test user."""
    return get_auth_token(test_user)


@pytest.fixture
def sample_template_id(auth_token):
    """Create a sample template for testing."""
    import requests

    template_def = {
        "name": "Test Template",
        "description": "Template for integration testing",
        "category": "test",
        "is_public": False,
        "template_definition": {
            "steps": [
                {
                    "id": "greeting",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "Say hello to {{ name }}"
                },
                {
                    "id": "farewell",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "Say goodbye to {{ name }}. Previous greeting was: {{ steps.greeting.output }}"
                }
            ]
        }
    }

    response = requests.post(
        f"{API_ENDPOINT}/templates",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json=template_def
    )

    assert response.status_code == 201
    template_id = response.json()['template_id']

    yield template_id

    # Cleanup: delete template
    requests.delete(
        f"{API_ENDPOINT}/templates/{template_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )


def test_template_test_mock_mode(auth_token, sample_template_id):
    """Test template testing in mock mode (no Bedrock calls)."""
    import requests

    response = requests.post(
        f"{API_ENDPOINT}/templates/{sample_template_id}/test",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json={
            "sample_data": {
                "name": "Alice"
            },
            "mock": True
        }
    )

    assert response.status_code == 200

    result = response.json()
    assert result['template_id'] == sample_template_id
    assert result['mock'] is True
    assert 'result' in result
    assert 'greeting' in result['result']
    assert 'farewell' in result['result']

    # Check mock output format
    greeting_result = result['result']['greeting']
    assert greeting_result['mocked'] is True
    assert 'prompt' in greeting_result
    assert 'output' in greeting_result
    assert 'MOCK OUTPUT' in greeting_result['output']

    # Check that prompt was rendered with sample data
    assert 'Alice' in greeting_result['prompt']


def test_template_test_missing_required_field(auth_token, sample_template_id):
    """Test template testing with missing required field."""
    import requests

    response = requests.post(
        f"{API_ENDPOINT}/templates/{sample_template_id}/test",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json={
            "sample_data": {},  # Missing 'name' field
            "mock": True
        }
    )

    assert response.status_code == 400
    assert 'Missing required fields' in response.json()['error']


def test_template_test_nonexistent_template(auth_token):
    """Test template testing with non-existent template ID."""
    import requests

    response = requests.post(
        f"{API_ENDPOINT}/templates/nonexistent-template-id/test",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json={
            "sample_data": {"name": "Bob"},
            "mock": True
        }
    )

    assert response.status_code == 404
    assert 'not found' in response.json()['error'].lower()


def test_template_test_unauthorized(sample_template_id):
    """Test template testing without authentication."""
    import requests

    response = requests.post(
        f"{API_ENDPOINT}/templates/{sample_template_id}/test",
        headers={"Content-Type": "application/json"},
        json={
            "sample_data": {"name": "Charlie"},
            "mock": True
        }
    )

    assert response.status_code == 401


def test_template_test_with_filters(auth_token):
    """Test template with custom filters."""
    import requests

    # Create template with filters
    template_def = {
        "name": "Filter Test Template",
        "description": "Template testing custom filters",
        "category": "test",
        "template_definition": {
            "steps": [
                {
                    "id": "test",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "Random sentence: {{ text | random_sentence }}"
                }
            ]
        }
    }

    create_response = requests.post(
        f"{API_ENDPOINT}/templates",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json=template_def
    )

    assert create_response.status_code == 201
    template_id = create_response.json()['template_id']

    # Test the template
    test_response = requests.post(
        f"{API_ENDPOINT}/templates/{template_id}/test",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json={
            "sample_data": {
                "text": "First sentence. Second sentence. Third sentence."
            },
            "mock": True
        }
    )

    assert test_response.status_code == 200
    result = test_response.json()

    # Check that filter was applied in rendered prompt
    rendered_prompt = result['result']['test']['prompt']
    assert 'sentence' in rendered_prompt.lower()

    # Cleanup
    requests.delete(
        f"{API_ENDPOINT}/templates/{template_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )


def test_template_test_with_conditionals(auth_token):
    """Test template with conditional logic."""
    import requests

    # Create template with conditionals
    template_def = {
        "name": "Conditional Test Template",
        "description": "Template testing conditionals",
        "category": "test",
        "template_definition": {
            "steps": [
                {
                    "id": "conditional",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "{% if genre == 'poetry' %}Write a poem{% else %}Write prose{% endif %} about {{ topic }}"
                }
            ]
        }
    }

    create_response = requests.post(
        f"{API_ENDPOINT}/templates",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json=template_def
    )

    assert create_response.status_code == 201
    template_id = create_response.json()['template_id']

    # Test with genre='poetry'
    test_response = requests.post(
        f"{API_ENDPOINT}/templates/{template_id}/test",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json={
            "sample_data": {
                "genre": "poetry",
                "topic": "autumn"
            },
            "mock": True
        }
    )

    assert test_response.status_code == 200
    result = test_response.json()
    rendered_prompt = result['result']['conditional']['prompt']
    assert 'Write a poem' in rendered_prompt
    assert 'Write prose' not in rendered_prompt

    # Cleanup
    requests.delete(
        f"{API_ENDPOINT}/templates/{template_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )


def test_template_test_prompt_metadata(auth_token, sample_template_id):
    """Test that template testing returns useful metadata about prompts."""
    import requests

    response = requests.post(
        f"{API_ENDPOINT}/templates/{sample_template_id}/test",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json={
            "sample_data": {"name": "David"},
            "mock": True
        }
    )

    assert response.status_code == 200
    result = response.json()

    # Check metadata is present
    greeting_result = result['result']['greeting']
    assert 'prompt_length' in greeting_result
    assert 'prompt_tokens_estimate' in greeting_result
    assert greeting_result['prompt_length'] > 0
    assert greeting_result['prompt_tokens_estimate'] > 0
