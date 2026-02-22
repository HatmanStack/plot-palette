"""Tests for list_versions Lambda handler — calls actual lambda_handler."""

import json
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/templates/list_versions.py")
lambda_handler = _mod.lambda_handler


def make_event(user_id="user-123", template_id="tmpl-abc"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"template_id": template_id},
    }


def _invoke(event, mock_table):
    """Invoke the actual lambda_handler with patched module-level clients."""
    _mod.templates_table = mock_table
    return lambda_handler(event, None)


class TestListVersionsHandler:
    def _make_versions(self, count=3, user_id="user-123", is_public=False):
        """Create mock template version items sorted newest first."""
        items = []
        for v in range(count, 0, -1):
            items.append(
                {
                    "template_id": "tmpl-abc",
                    "version": v,
                    "name": f"Template v{v}",
                    "description": f"Version {v} description",
                    "user_id": user_id,
                    "is_public": is_public,
                    "created_at": f"2025-01-{v:02d}T00:00:00",
                    "steps": [{"id": "step1", "model": "test", "prompt": "test"}],
                }
            )
        return items

    def test_list_versions_success(self):
        """Invoke actual handler: 3 versions -> sorted desc, no steps in response."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": self._make_versions(3)}

        result = _invoke(make_event(), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["versions"]) == 3
        assert body["versions"][0]["version"] == 3
        assert body["versions"][2]["version"] == 1
        for v in body["versions"]:
            assert "steps" not in v
        assert body["template_id"] == "tmpl-abc"

    def test_list_versions_not_owner_private(self):
        """Invoke actual handler: private template, different user -> 403."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": self._make_versions(2, user_id="other-user", is_public=False)
        }

        result = _invoke(make_event(), mock_table)

        assert result["statusCode"] == 403

    def test_list_versions_not_owner_public(self):
        """Invoke actual handler: public template, different user -> 200."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": self._make_versions(2, user_id="other-user", is_public=True)
        }

        result = _invoke(make_event(), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["versions"]) == 2

    def test_list_versions_not_found(self):
        """Invoke actual handler: empty query -> 404."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = _invoke(make_event(), mock_table)

        assert result["statusCode"] == 404

    def test_list_versions_missing_path_params(self):
        """Invoke actual handler: missing pathParameters -> 400."""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}}
            }
        }

        result = _invoke(event, MagicMock())

        assert result["statusCode"] == 400
