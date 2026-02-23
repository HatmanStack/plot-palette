"""
Plot Palette - Update Notification Preferences Lambda Handler

PUT /settings/notifications endpoint that upserts notification preferences
for the authenticated user.
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

from boto3.dynamodb.conditions import Attr  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from lambda_responses import error_response, success_response
from models import NotificationPreferences
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
prefs_table = dynamodb.Table(
    os.environ.get("NOTIFICATION_PREFERENCES_TABLE_NAME", "plot-palette-NotificationPreferences")
)

ALLOWED_FIELDS = {
    "email_enabled",
    "email_address",
    "webhook_enabled",
    "webhook_url",
    "notify_on_complete",
    "notify_on_failure",
    "notify_on_budget_exceeded",
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for PUT /settings/notifications endpoint.

    Upserts notification preferences for the authenticated user.
    """
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        logger.info(json.dumps({"event": "update_preferences_request", "user_id": user_id}))

        # Parse request body
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Filter to allowed fields only
        updates = {k: v for k, v in body.items() if k in ALLOWED_FIELDS}

        if not updates:
            return error_response(400, "No valid preference fields provided")

        # Validate webhook URL if provided
        webhook_url = updates.get("webhook_url")
        if webhook_url is not None and webhook_url != "" and not webhook_url.startswith("https://"):
            return error_response(400, "Webhook URL must start with https://")

        # Fetch existing preferences or start with defaults
        existing_response = prefs_table.get_item(Key={"user_id": user_id})
        if "Item" in existing_response:
            existing = existing_response["Item"]
        else:
            existing = {
                "user_id": user_id,
                "email_enabled": False,
                "email_address": None,
                "webhook_enabled": False,
                "webhook_url": None,
                "notify_on_complete": True,
                "notify_on_failure": True,
                "notify_on_budget_exceeded": True,
            }

        # Merge updates
        existing.update(updates)
        existing["user_id"] = user_id
        existing["updated_at"] = datetime.now(UTC).isoformat()

        # Validate full model
        try:
            prefs = NotificationPreferences(
                user_id=user_id,
                email_enabled=existing.get("email_enabled", False),
                email_address=existing.get("email_address"),
                webhook_enabled=existing.get("webhook_enabled", False),
                webhook_url=existing.get("webhook_url"),
                notify_on_complete=existing.get("notify_on_complete", True),
                notify_on_failure=existing.get("notify_on_failure", True),
                notify_on_budget_exceeded=existing.get("notify_on_budget_exceeded", True),
            )
        except ValueError as e:
            return error_response(400, str(e))

        # Save to DynamoDB with optimistic locking
        expected_updated_at = existing.get("updated_at") if "Item" in existing_response else None
        put_kwargs: dict[str, Any] = {"Item": prefs.to_table_item()}
        if expected_updated_at:
            put_kwargs["ConditionExpression"] = Attr("updated_at").eq(expected_updated_at)
        else:
            put_kwargs["ConditionExpression"] = Attr("user_id").not_exists()
        try:
            prefs_table.put_item(**put_kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return error_response(409, "Preferences were modified concurrently, please retry")
            raise

        logger.info(json.dumps({"event": "preferences_updated", "user_id": user_id}))

        return success_response(200, {
            "email_enabled": prefs.email_enabled,
            "email_address": prefs.email_address,
            "webhook_enabled": prefs.webhook_enabled,
            "webhook_url": prefs.webhook_url,
            "notify_on_complete": prefs.notify_on_complete,
            "notify_on_failure": prefs.notify_on_failure,
            "notify_on_budget_exceeded": prefs.notify_on_budget_exceeded,
        })

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
