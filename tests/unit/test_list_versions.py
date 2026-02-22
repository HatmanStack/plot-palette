"""Tests for list_versions Lambda handler logic."""

import json
from unittest.mock import MagicMock

from backend.shared.lambda_responses import error_response, success_response
from backend.shared.utils import sanitize_error_message


def make_event(user_id="user-123", template_id="tmpl-abc"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"template_id": template_id},
    }


def simulate_list_versions_handler(event, templates_table_mock):
    """
    Simulate list_versions handler logic without importing the Lambda module.
    """
    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        template_id = event["pathParameters"]["template_id"]

        from boto3.dynamodb.conditions import Key

        response = templates_table_mock.query(
            KeyConditionExpression=Key("template_id").eq(template_id),
            ScanIndexForward=False,
        )

        items = response.get("Items", [])

        if not items:
            return error_response(404, "Template not found")

        # Check ownership or public on first item (all versions share user_id)
        first = items[0]
        if first["user_id"] != user_id and not first.get("is_public", False):
            return error_response(403, "Access denied - template is private")

        # Build version summaries (omit template_definition / steps)
        versions = []
        for item in items:
            versions.append(
                {
                    "version": item["version"],
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "created_at": str(item.get("created_at", "")),
                }
            )

        return success_response(200, {"versions": versions, "template_id": template_id})

    except KeyError as e:
        return error_response(
            400, f"Missing required field: {sanitize_error_message(str(e))}"
        )

    except Exception:
        return error_response(500, "Internal server error")


class TestListVersionsLogic:
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
        """Mock query returning 3 versions. Assert sorted desc, no steps in response."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": self._make_versions(3)}

        result = simulate_list_versions_handler(make_event(), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["versions"]) == 3
        assert body["versions"][0]["version"] == 3
        assert body["versions"][2]["version"] == 1
        # Verify steps are NOT included in response
        for v in body["versions"]:
            assert "steps" not in v
        assert body["template_id"] == "tmpl-abc"

    def test_list_versions_not_owner_private(self):
        """Mock private template owned by different user. Assert 403."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": self._make_versions(2, user_id="other-user", is_public=False)
        }

        result = simulate_list_versions_handler(make_event(), mock_table)

        assert result["statusCode"] == 403

    def test_list_versions_not_owner_public(self):
        """Mock public template owned by different user. Assert 200."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": self._make_versions(2, user_id="other-user", is_public=True)
        }

        result = simulate_list_versions_handler(make_event(), mock_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["versions"]) == 2

    def test_list_versions_not_found(self):
        """Mock empty query result. Assert 404."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = simulate_list_versions_handler(make_event(), mock_table)

        assert result["statusCode"] == 404

    def test_list_versions_missing_path_params(self):
        """Missing path parameters should return 400."""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}}
            }
        }

        result = simulate_list_versions_handler(event, MagicMock())

        assert result["statusCode"] == 400
