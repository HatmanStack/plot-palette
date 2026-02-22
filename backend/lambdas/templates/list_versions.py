"""
Plot Palette - List Template Versions Lambda Handler

GET /templates/{template_id}/versions endpoint that returns all versions
of a template, sorted newest first, with summary metadata only.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))

# Fields to include in version summaries (omit steps/template_definition for size)
SUMMARY_FIELDS = {"version", "name", "description", "created_at"}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /templates/{template_id}/versions endpoint.

    Returns all versions of a template sorted newest first with summary metadata.
    Only the owner or anyone (for public templates) can access.
    """
    try:
        set_correlation_id(extract_request_id(event))

        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        template_id = event["pathParameters"]["template_id"]

        logger.info(
            json.dumps(
                {
                    "event": "list_versions_request",
                    "user_id": user_id,
                    "template_id": template_id,
                }
            )
        )

        # Query all versions of this template, sorted newest first
        try:
            response = templates_table.query(
                KeyConditionExpression=Key("template_id").eq(template_id),
                ScanIndexForward=False,
            )
        except ClientError as e:
            logger.error(json.dumps({"event": "query_error", "error": str(e)}))
            return error_response(500, "Error retrieving template versions")

        items = response.get("Items", [])

        if not items:
            return error_response(404, "Template not found")

        # Authorization check: use first item (all versions share same user_id)
        first = items[0]
        if first["user_id"] != user_id and not first.get("is_public", False):
            logger.warning(
                json.dumps(
                    {
                        "event": "unauthorized_version_list",
                        "user_id": user_id,
                        "template_id": template_id,
                    }
                )
            )
            return error_response(403, "Access denied - template is private")

        # Build version summaries (omit full template definition)
        versions = []
        for item in items:
            summary = {
                "version": item["version"],
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "created_at": str(item.get("created_at", "")),
            }
            versions.append(summary)

        logger.info(
            json.dumps(
                {
                    "event": "list_versions_success",
                    "template_id": template_id,
                    "version_count": len(versions),
                }
            )
        )

        return success_response(200, {"versions": versions, "template_id": template_id})

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
