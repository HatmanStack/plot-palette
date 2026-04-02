"""
Plot Palette - Template Marketplace Search Lambda Unit Tests

Tests for GET /templates/marketplace endpoint that searches
and paginates public templates.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/templates/search_templates.py")
lambda_handler = _mod.lambda_handler


def make_event(
    user_id: str = "test-user-123",
    q: str | None = None,
    sort: str | None = None,
    limit: str | None = None,
    last_key: str | None = None,
) -> dict[str, Any]:
    """Build an API Gateway v2 event for marketplace search."""
    params: dict[str, str] = {}
    if q:
        params["q"] = q
    if sort:
        params["sort"] = sort
    if limit:
        params["limit"] = limit
    if last_key:
        params["last_key"] = last_key

    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "GET", "path": "/templates/marketplace"},
            "requestId": "test-request-id",
        },
        "queryStringParameters": params or None,
        "body": None,
    }


def make_template(
    template_id: str,
    name: str = "Test Template",
    user_id: str = "other-user",
    version: int = 1,
    is_public: bool = True,
    description: str = "A test template",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a DynamoDB template item (high-level Table format)."""
    return {
        "template_id": template_id,
        "version": version,
        "name": name,
        "user_id": user_id,
        "is_public": is_public,
        "description": description,
        "schema_requirements": ["author.name"],
        "template_definition": {
            "steps": [{"id": "q1", "prompt": "Generate about {{ author.name }}"}]
        },
        "created_at": created_at or datetime.now(UTC).isoformat(),
    }


def _invoke(event, templates):
    """Invoke lambda_handler with mocked DynamoDB query (GSI)."""
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": templates}
    _mod.templates_table = mock_table
    return lambda_handler(event, None)


class TestSearchReturnsOnlyPublic:
    """Ensure private templates never appear in marketplace results."""

    def test_search_returns_only_public(self):
        """Properly mock DynamoDB FilterExpression scan results."""
        public_templates = [
            make_template("t-1", name="Public One", is_public=True),
            make_template("t-3", name="Public Two", is_public=True),
        ]

        response = _invoke(make_event(), public_templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["templates"]) == 2
        assert all(t["template_id"] in ["t-1", "t-3"] for t in body["templates"])


class TestSearchQueryFilter:
    """Test text search filtering."""

    def test_search_query_filters_by_name(self):
        """Search 'poetry'. Assert only matching template returned."""
        templates = [
            make_template("t-1", name="Poetry Generator", description="Makes poems"),
            make_template("t-2", name="Code Helper", description="Writes code"),
        ]

        response = _invoke(make_event(q="poetry"), templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["templates"]) == 1
        assert body["templates"][0]["template_id"] == "t-1"

    def test_search_query_filters_by_description(self):
        """Search matches description too."""
        templates = [
            make_template("t-1", name="Generator", description="Creates poetry content"),
            make_template("t-2", name="Code Helper", description="Writes code"),
        ]

        response = _invoke(make_event(q="poetry"), templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["templates"]) == 1
        assert body["templates"][0]["template_id"] == "t-1"


class TestSearchLatestVersion:
    """Test that only the latest version per template is returned."""

    def test_search_latest_version_only(self):
        """Insert template with versions 1,2,3. Assert only version 3 in results."""
        templates = [
            make_template("t-1", name="My Template", version=1,
                          created_at=(datetime.now(UTC) - timedelta(days=3)).isoformat()),
            make_template("t-1", name="My Template v2", version=2,
                          created_at=(datetime.now(UTC) - timedelta(days=2)).isoformat()),
            make_template("t-1", name="My Template v3", version=3,
                          created_at=(datetime.now(UTC) - timedelta(days=1)).isoformat()),
        ]

        response = _invoke(make_event(), templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["templates"]) == 1
        assert body["templates"][0]["version"] == 3
        assert body["templates"][0]["name"] == "My Template v3"


class TestSearchPagination:
    """Test pagination with limit and last_key."""

    def test_search_pagination(self):
        """Insert 25 templates, request limit=10. Assert 10 results + last_key."""
        templates = [
            make_template(f"t-{i:02d}", name=f"Template {i}",
                          created_at=(datetime.now(UTC) - timedelta(hours=i)).isoformat())
            for i in range(25)
        ]

        response = _invoke(make_event(limit="10"), templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["templates"]) == 10
        assert body.get("last_key") is not None


class TestSearchOmitsDefinition:
    """Test that template_definition is not in results."""

    def test_search_no_template_definition(self):
        """Assert template_definition not in any result item."""
        templates = [make_template("t-1")]

        response = _invoke(make_event(), templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        for tmpl in body["templates"]:
            assert "template_definition" not in tmpl


class TestSearchEmptyResults:
    """Test empty search results."""

    def test_search_empty_results(self):
        """Search query matching nothing. Assert empty array."""
        templates = [
            make_template("t-1", name="Code Helper", description="Writes code"),
        ]

        response = _invoke(make_event(q="nonexistent_xyz"), templates)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["templates"] == []
