"""
Plot Palette - Update Template Lambda Handler

PUT /templates/{template_id} endpoint that creates a new version of a template
(immutable versioning pattern).
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from template_filters import validate_template_syntax
from utils import extract_schema_requirements, sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))


def get_latest_version(template_id: str) -> int:
    """Get the latest version number for a template."""
    try:
        response = templates_table.query(
            KeyConditionExpression=Key("template_id").eq(template_id),
            ScanIndexForward=False,  # Descending order
            Limit=1,
        )

        items = response.get("Items", [])
        if items:
            return items[0].get("version", 1)
        return 1

    except ClientError:
        return 1


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for PUT /templates/{template_id} endpoint.

    Creates a new version of the template (immutable updates).

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with new version info
    """
    try:
        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        # Extract template ID from path parameters
        template_id = event["pathParameters"]["template_id"]

        logger.info(
            json.dumps(
                {"event": "update_template_request", "user_id": user_id, "template_id": template_id}
            )
        )

        # Parse request body
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Get current template to verify ownership (get latest version)
        try:
            current_response = templates_table.query(
                KeyConditionExpression=Key("template_id").eq(template_id),
                ScanIndexForward=False,  # Descending order to get latest version
                Limit=1,
            )

            if not current_response.get("Items"):
                return error_response(404, "Template not found")

            current_template = current_response["Items"][0]

            # Check ownership
            if current_template["user_id"] != user_id:
                return error_response(403, "Access denied - you do not own this template")

        except ClientError as e:
            logger.error(json.dumps({"event": "get_current_template_error", "error": str(e)}))
            return error_response(500, "Error retrieving template")

        # Validate required fields
        if "name" not in body and "template_definition" not in body:
            return error_response(400, "Must provide at least name or template_definition")

        # Use existing values if not provided
        name = body.get("name", current_template["name"])
        template_def = body.get("template_definition", current_template["template_definition"])

        # Validate Jinja2 syntax first
        try:
            valid, error_msg = validate_template_syntax(template_def)
            if not valid:
                return error_response(400, f"Template validation failed: {error_msg}")
        except Exception as e:
            return error_response(400, f"Template validation error: {str(e)}")

        # Extract schema requirements
        try:
            schema_reqs = extract_schema_requirements(template_def)
        except ValueError as e:
            return error_response(400, str(e))

        # Get next version number
        latest_version = get_latest_version(template_id)
        new_version = latest_version + 1

        now = datetime.now(UTC).isoformat()

        # Create new version
        new_template = {
            "template_id": template_id,
            "version": new_version,
            "name": name,
            "user_id": user_id,
            "template_definition": template_def,
            "schema_requirements": schema_reqs,
            "created_at": now,
            "is_public": body.get("is_public", current_template.get("is_public", False)),
            "description": body.get("description", current_template.get("description", "")),
        }

        # Insert new version
        try:
            templates_table.put_item(Item=new_template)
        except ClientError as e:
            logger.error(json.dumps({"event": "template_update_error", "error": str(e)}))
            return error_response(500, "Error updating template")

        logger.info(
            json.dumps(
                {
                    "event": "template_updated",
                    "template_id": template_id,
                    "previous_version": latest_version,
                    "new_version": new_version,
                }
            )
        )

        return success_response(
            200,
            {
                "template_id": template_id,
                "version": new_version,
                "previous_version": latest_version,
                "schema_requirements": schema_reqs,
                "message": "Template updated successfully",
            },
        )

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
