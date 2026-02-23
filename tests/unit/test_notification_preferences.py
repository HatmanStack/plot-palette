"""
Unit tests for notification preferences CRUD endpoints.

Tests get_preferences and update_preferences Lambda handlers.
"""

import json
import os
from unittest.mock import patch

from tests.unit.handler_import import load_handler

# Load handlers
_get_mod = load_handler("lambdas/settings/get_preferences.py")
get_handler = _get_mod.lambda_handler

_update_mod = load_handler("lambdas/settings/update_preferences.py")
update_handler = _update_mod.lambda_handler


def _make_event(user_id="user-123", body=None, method="GET"):
    event = {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "queryStringParameters": None,
        "body": json.dumps(body) if body else None,
    }
    return event


class TestGetPreferences:
    def test_get_preferences_default(self):
        """No saved prefs. Assert defaults returned."""
        mock_table = _get_mod.prefs_table
        mock_table.get_item.return_value = {}

        response = get_handler(_make_event(user_id="user-new"), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["email_enabled"] is False
        assert body["email_address"] is None
        assert body["webhook_enabled"] is False
        assert body["webhook_url"] is None
        assert body["notify_on_complete"] is True
        assert body["notify_on_failure"] is True
        assert body["notify_on_budget_exceeded"] is True

    def test_get_preferences_saved(self):
        """Saved prefs exist. Assert correct values returned."""
        mock_table = _get_mod.prefs_table
        mock_table.get_item.return_value = {
            "Item": {
                "user_id": "user-123",
                "email_enabled": True,
                "email_address": "user@example.com",
                "webhook_enabled": True,
                "webhook_url": "https://hooks.example.com/notify",
                "notify_on_complete": True,
                "notify_on_failure": False,
                "notify_on_budget_exceeded": True,
                "updated_at": "2026-02-22T12:00:00+00:00",
            }
        }

        response = get_handler(_make_event(user_id="user-123"), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["email_enabled"] is True
        assert body["email_address"] == "user@example.com"
        assert body["webhook_enabled"] is True
        assert body["webhook_url"] == "https://hooks.example.com/notify"
        assert body["notify_on_failure"] is False


class TestUpdatePreferences:
    def test_update_preferences_success(self):
        """PUT with email_enabled=true. Assert saved."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        response = update_handler(
            _make_event(
                user_id="user-123",
                body={"email_enabled": True, "email_address": "user@example.com"},
                method="PUT",
            ),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["email_enabled"] is True
        assert body["email_address"] == "user@example.com"
        mock_table.put_item.assert_called_once()

    @patch("socket.gethostbyname", return_value="93.184.216.34")
    def test_update_preferences_webhook_https(self, mock_dns):
        """PUT with https:// URL resolving to public IP. Assert success."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        response = update_handler(
            _make_event(
                user_id="user-123",
                body={"webhook_enabled": True, "webhook_url": "https://hooks.example.com/notify"},
            ),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["webhook_url"] == "https://hooks.example.com/notify"

    @patch("socket.gethostbyname", return_value="127.0.0.1")
    def test_update_preferences_webhook_loopback(self, mock_dns):
        """PUT with webhook URL resolving to loopback. Assert 400."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {}

        response = update_handler(
            _make_event(
                user_id="user-123",
                body={"webhook_enabled": True, "webhook_url": "https://evil.com/steal"},
            ),
            None,
        )

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "private" in body["error"].lower() or "reserved" in body["error"].lower()

    @patch("socket.gethostbyname", return_value="169.254.169.254")
    def test_update_preferences_webhook_metadata_endpoint(self, mock_dns):
        """PUT with webhook URL resolving to AWS metadata endpoint. Assert 400."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {}

        response = update_handler(
            _make_event(
                user_id="user-123",
                body={"webhook_enabled": True, "webhook_url": "https://evil.com/ssrf"},
            ),
            None,
        )

        assert response["statusCode"] == 400

    @patch("socket.gethostbyname", return_value="10.0.0.1")
    def test_update_preferences_webhook_private_ip(self, mock_dns):
        """PUT with webhook URL resolving to private IP. Assert 400."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {}

        response = update_handler(
            _make_event(
                user_id="user-123",
                body={"webhook_enabled": True, "webhook_url": "https://internal.corp/hook"},
            ),
            None,
        )

        assert response["statusCode"] == 400

    def test_update_preferences_webhook_http(self):
        """PUT with http:// URL. Assert 400."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {}

        response = update_handler(
            _make_event(
                user_id="user-123",
                body={"webhook_enabled": True, "webhook_url": "http://hooks.example.com/notify"},
            ),
            None,
        )

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "https" in body["error"].lower()

    def test_update_preferences_partial(self):
        """PUT with only one field. Assert other fields preserved."""
        mock_table = _update_mod.prefs_table
        mock_table.get_item.return_value = {
            "Item": {
                "user_id": "user-123",
                "email_enabled": True,
                "email_address": "user@example.com",
                "webhook_enabled": False,
                "webhook_url": None,
                "notify_on_complete": True,
                "notify_on_failure": True,
                "notify_on_budget_exceeded": True,
                "updated_at": "2026-02-22T12:00:00+00:00",
            }
        }
        mock_table.put_item.return_value = {}

        response = update_handler(
            _make_event(user_id="user-123", body={"notify_on_failure": False}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["notify_on_failure"] is False
        # Original values preserved
        assert body["email_enabled"] is True
        assert body["email_address"] == "user@example.com"

    def test_update_preferences_no_valid_fields(self):
        """PUT with no valid fields. Assert 400."""
        mock_table = _update_mod.prefs_table

        response = update_handler(
            _make_event(user_id="user-123", body={"invalid_field": True}),
            None,
        )

        assert response["statusCode"] == 400

    def test_update_preferences_empty_body(self):
        """PUT with empty body. Assert 400."""
        response = update_handler(
            _make_event(user_id="user-123", body={}),
            None,
        )

        assert response["statusCode"] == 400
