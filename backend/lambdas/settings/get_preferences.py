"""
Plot Palette - Get Notification Preferences Lambda Handler

GET /settings/notifications endpoint that retrieves notification preferences
for the authenticated user.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from lambda_responses import error_response, success_response
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
prefs_table = dynamodb.Table(
    os.environ.get("NOTIFICATION_PREFERENCES_TABLE_NAME", "plot-palette-NotificationPreferences")
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /settings/notifications endpoint.

    Returns the user's notification preferences, or defaults if none saved.
    """
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        logger.info(json.dumps({"event": "get_preferences_request", "user_id": user_id}))

        response = prefs_table.get_item(Key={"user_id": user_id})

        if "Item" not in response:
            # Return defaults
            return success_response(200, {
                "email_enabled": False,
                "email_address": None,
                "webhook_enabled": False,
                "webhook_url": None,
                "notify_on_complete": True,
                "notify_on_failure": True,
                "notify_on_budget_exceeded": True,
            })

        item = response["Item"]
        return success_response(200, {
            "email_enabled": item.get("email_enabled", False),
            "email_address": item.get("email_address"),
            "webhook_enabled": item.get("webhook_enabled", False),
            "webhook_url": item.get("webhook_url"),
            "notify_on_complete": item.get("notify_on_complete", True),
            "notify_on_failure": item.get("notify_on_failure", True),
            "notify_on_budget_exceeded": item.get("notify_on_budget_exceeded", True),
        })

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
