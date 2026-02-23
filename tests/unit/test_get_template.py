"""Tests for get_template Lambda handler — calls actual lambda_handler."""

import json
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/templates/get_template.py")
lambda_handler = _mod.lambda_handler


def make_event(user_id="user-123", template_id="tmpl-abc", version=None):
    event = {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"template_id": template_id},
        "queryStringParameters": {},
    }
    if version is not None:
        event["queryStringParameters"]["version"] = str(version)
    return event


def _invoke(event, mock_table):
    """Invoke the actual lambda_handler with patched module-level clients."""
    _mod.templates_table = mock_table
    return lambda_handler(event, None)


class TestGetTemplateHandler:
    def _template(self, version=1, user_id="user-123"):
        return {
            "template_id": "tmpl-abc",
            "version": version,
            "name": f"Template v{version}",
            "user_id": user_id,
            "is_public": False,
            "steps": [{"id": "step1", "model": "test", "prompt": "test"}],
            "created_at": "2025-01-01T00:00:00",
        }

    def test_get_template_latest_version(self):
        """Invoke actual handler: version=latest -> returns version 3."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [self._template(3)]}

        result = _invoke(make_event(version="latest"), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version"] == 3
        assert body["is_owner"] is True

    def test_get_template_specific_version(self):
        """Invoke actual handler: version=2 -> returns version 2."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._template(2)}

        result = _invoke(make_event(version="2"), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version"] == 2

    def test_get_template_default_version(self):
        """Invoke actual handler: no version param -> returns version 1."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._template(1)}

        result = _invoke(make_event(), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version"] == 1

    def test_get_template_latest_not_found(self):
        """Invoke actual handler: version=latest, no versions -> 404."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = _invoke(make_event(version="latest"), mock_table)

        assert result["statusCode"] == 404

    def test_get_template_invalid_version(self):
        """Invoke actual handler: version=abc -> 400."""
        mock_table = MagicMock()

        result = _invoke(make_event(version="abc"), mock_table)

        assert result["statusCode"] == 400

    def test_get_template_private_not_owner(self):
        """Invoke actual handler: private template, different user -> 403."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._template(1, user_id="other-user")}

        result = _invoke(make_event(), mock_table)

        assert result["statusCode"] == 403

    def test_get_template_not_found(self):
        """Invoke actual handler: no Item -> 404."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = _invoke(make_event(version="1"), mock_table)

        assert result["statusCode"] == 404
