"""Tests for get_template Lambda handler logic — including version=latest support."""

import json
from unittest.mock import MagicMock

from backend.shared.lambda_responses import error_response, success_response
from backend.shared.utils import sanitize_error_message


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


def simulate_get_template_handler(event, templates_table_mock):
    """
    Simulate get_template handler logic with version=latest support.
    """
    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        template_id = event["pathParameters"]["template_id"]

        params = event.get("queryStringParameters") or {}
        version_str = params.get("version", "1")

        if version_str == "latest":
            # Query for latest version
            from boto3.dynamodb.conditions import Key

            response = templates_table_mock.query(
                KeyConditionExpression=Key("template_id").eq(template_id),
                ScanIndexForward=False,
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                return error_response(404, "Template not found")
            template = items[0]
        else:
            try:
                version = int(version_str)
                if version < 1:
                    return error_response(
                        400, "Invalid version parameter: must be a positive integer"
                    )
            except (ValueError, TypeError):
                return error_response(
                    400, "Invalid version parameter: must be a positive integer"
                )

            response = templates_table_mock.get_item(
                Key={"template_id": template_id, "version": version}
            )

            if "Item" not in response:
                return error_response(404, "Template not found")

            template = response["Item"]

        # Authorization check
        if template["user_id"] != user_id and not template.get("is_public", False):
            return error_response(403, "Access denied - template is private")

        template["is_owner"] = template["user_id"] == user_id

        return success_response(200, template, default=str)

    except KeyError as e:
        return error_response(
            400, f"Missing required field: {sanitize_error_message(str(e))}"
        )

    except Exception:
        return error_response(500, "Internal server error")


class TestGetTemplateLatestVersion:
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
        """Mock query with ScanIndexForward=False. Assert returns version 3 (latest)."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [self._template(3)]}

        result = simulate_get_template_handler(
            make_event(version="latest"), mock_table
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version"] == 3
        assert body["is_owner"] is True

    def test_get_template_specific_version(self):
        """Assert version=2 returns version 2."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._template(2)}

        result = simulate_get_template_handler(
            make_event(version="2"), mock_table
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version"] == 2

    def test_get_template_default_version(self):
        """Default (no version param) returns version 1."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._template(1)}

        result = simulate_get_template_handler(make_event(), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version"] == 1

    def test_get_template_latest_not_found(self):
        """version=latest with no versions returns 404."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = simulate_get_template_handler(
            make_event(version="latest"), mock_table
        )

        assert result["statusCode"] == 404

    def test_get_template_invalid_version(self):
        """Invalid version parameter returns 400."""
        mock_table = MagicMock()

        result = simulate_get_template_handler(
            make_event(version="abc"), mock_table
        )

        assert result["statusCode"] == 400
