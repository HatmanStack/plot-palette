"""
Plot Palette - Template Fork Lambda Unit Tests

Tests for POST /templates/{template_id}/fork endpoint that copies
a public template into the authenticated user's collection.
"""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/templates/fork_template.py")
lambda_handler = _mod.lambda_handler


def make_event(
    user_id: str = "test-user-123",
    template_id: str = "tmpl-source",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an API Gateway v2 event for template fork."""
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "POST", "path": f"/templates/{template_id}/fork"},
            "requestId": "test-request-id",
        },
        "pathParameters": {"template_id": template_id},
        "queryStringParameters": None,
        "body": json.dumps(body) if body else None,
    }


def make_source_template(
    template_id: str = "tmpl-source",
    name: str = "Source Template",
    user_id: str = "other-user",
    is_public: bool = True,
    version: int = 3,
) -> dict[str, Any]:
    """Create a source template item."""
    return {
        "template_id": template_id,
        "version": version,
        "name": name,
        "user_id": user_id,
        "is_public": is_public,
        "description": "A great template",
        "schema_requirements": ["author.name", "author.bio"],
        "template_definition": {
            "steps": [
                {"id": "q1", "prompt": "Tell me about {{ author.name }}"},
                {"id": "q2", "prompt": "Based on {{ steps.q1.output }}"},
            ]
        },
        "created_at": datetime.now(UTC).isoformat(),
    }


def _invoke(event, source_template=None, query_versions=None):
    """Invoke lambda_handler with mocked DynamoDB table."""
    mock_table = MagicMock()

    if source_template is None and query_versions is None:
        # No template found
        mock_table.query.return_value = {"Items": []}
    elif query_versions is not None:
        mock_table.query.return_value = {"Items": query_versions}
    else:
        mock_table.query.return_value = {"Items": [source_template]}

    mock_table.put_item.return_value = {}

    _mod.templates_table = mock_table
    return lambda_handler(event, None), mock_table


class TestForkPublicTemplate:
    """Test successful fork of a public template."""

    def test_fork_public_template_success(self):
        """Fork a public template. Assert new template_id, user_id matches caller, version=1."""
        source = make_source_template()

        with patch.object(_mod, "generate_template_id",
                    return_value="new-tmpl-id"):
            response, mock_table = _invoke(make_event(), source)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["template_id"] == "new-tmpl-id"
        assert body["version"] == 1
        assert "forked" in body["message"].lower()

        # Verify put_item was called with correct data
        put_call = mock_table.put_item.call_args
        item = put_call.kwargs.get("Item") or put_call[1].get("Item")
        assert item["template_id"] == "new-tmpl-id"
        assert item["user_id"] == "test-user-123"
        assert item["version"] == 1
        assert item["is_public"] is False
        assert item["template_definition"] == source["template_definition"]
        assert item["schema_requirements"] == source["schema_requirements"]


class TestForkPrivateNotOwner:
    """Test that forking another user's private template is denied."""

    def test_fork_private_template_not_owner(self):
        """Attempt to fork another user's private template. Assert 403."""
        source = make_source_template(is_public=False, user_id="other-user")

        response, _ = _invoke(make_event(user_id="test-user-123"), source)

        assert response["statusCode"] == 403


class TestForkOwnTemplate:
    """Test forking your own template."""

    def test_fork_own_template(self):
        """Fork your own template (even if private). Assert success."""
        source = make_source_template(user_id="test-user-123", is_public=False)

        with patch.object(_mod, "generate_template_id",
                    return_value="new-tmpl-id"):
            response, _ = _invoke(make_event(user_id="test-user-123"), source)

        assert response["statusCode"] == 201


class TestForkCustomName:
    """Test name override on fork."""

    def test_fork_custom_name(self):
        """Provide name override. Assert new template uses it."""
        source = make_source_template(name="Original Name")

        with patch.object(_mod, "generate_template_id",
                    return_value="new-tmpl-id"):
            response, mock_table = _invoke(
                make_event(body={"name": "My Custom Name"}), source
            )

        assert response["statusCode"] == 201
        put_call = mock_table.put_item.call_args
        item = put_call.kwargs.get("Item") or put_call[1].get("Item")
        assert item["name"] == "My Custom Name"


class TestForkDefaultName:
    """Test default name when no override provided."""

    def test_fork_default_name(self):
        """No name override. Assert name is '{original} (fork)'."""
        source = make_source_template(name="Poetry Generator")

        with patch.object(_mod, "generate_template_id",
                    return_value="new-tmpl-id"):
            response, mock_table = _invoke(make_event(), source)

        assert response["statusCode"] == 201
        put_call = mock_table.put_item.call_args
        item = put_call.kwargs.get("Item") or put_call[1].get("Item")
        assert item["name"] == "Poetry Generator (fork)"


class TestForkNotFound:
    """Test fork of nonexistent template."""

    def test_fork_not_found(self):
        """Fork nonexistent template. Assert 404."""
        response, _ = _invoke(make_event(template_id="nonexistent"), None)

        assert response["statusCode"] == 404
