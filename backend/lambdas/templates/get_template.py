"""
Plot Palette - Get Template Lambda Handler

GET /templates/{template_id} endpoint that retrieves full template details
including the complete template definition.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /templates/{template_id} endpoint.

    Retrieves full template details including definition. Supports version
    query parameter to get specific versions.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with full template details
    """
    try:
        set_correlation_id(extract_request_id(event))

        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        # Extract template ID from path parameters
        template_id = event["pathParameters"]["template_id"]

        # Parse query parameters
        params = event.get("queryStringParameters") or {}
        try:
            version = int(params.get("version", 1))
            if version < 1:
                return error_response(400, "Invalid version parameter: must be a positive integer")
        except (ValueError, TypeError):
            return error_response(400, "Invalid version parameter: must be a positive integer")

        logger.info(
            json.dumps(
                {
                    "event": "get_template_request",
                    "user_id": user_id,
                    "template_id": template_id,
                    "version": version,
                }
            )
        )

        # Get template from DynamoDB
        try:
            response = templates_table.get_item(
                Key={"template_id": template_id, "version": version}
            )
        except ClientError as e:
            logger.error(json.dumps({"event": "get_template_error", "error": str(e)}))
            return error_response(500, "Error retrieving template")

        if "Item" not in response:
            return error_response(404, "Template not found")

        template = response["Item"]

        # Authorization check - only owner or public templates can be accessed
        if template["user_id"] != user_id and not template.get("is_public", False):
            logger.warning(
                json.dumps(
                    {
                        "event": "unauthorized_template_access",
                        "user_id": user_id,
                        "template_id": template_id,
                        "template_owner": template["user_id"],
                    }
                )
            )
            return error_response(403, "Access denied - template is private")

        # Add ownership flag
        template["is_owner"] = template["user_id"] == user_id

        logger.info(
            json.dumps(
                {"event": "get_template_success", "user_id": user_id, "template_id": template_id}
            )
        )

        return success_response(200, template, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
