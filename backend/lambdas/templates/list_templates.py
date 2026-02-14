"""
Plot Palette - List Templates Lambda Handler

GET /templates endpoint that lists templates for the authenticated user
and public templates from all users.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /templates endpoint.

    Lists user's templates and public templates from other users.
    Returns only the latest version of each template.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with list of templates
    """
    try:
        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        logger.info(json.dumps({"event": "list_templates_request", "user_id": user_id}))

        # Parse query parameters
        params = event.get("queryStringParameters") or {}
        include_public = params.get("include_public", "true").lower() == "true"

        # Get user's templates
        try:
            user_response = templates_table.query(
                IndexName="user-id-index", KeyConditionExpression=Key("user_id").eq(user_id)
            )
            user_templates = user_response.get("Items", [])
        except ClientError as e:
            logger.error(json.dumps({"event": "query_user_templates_error", "error": str(e)}))
            return error_response(500, "Error querying user templates")

        all_templates = user_templates.copy()

        # Get public templates if requested
        if include_public:
            try:
                public_response = templates_table.scan(
                    FilterExpression=Attr("is_public").eq(True) & Attr("user_id").ne(user_id)
                )
                public_templates = public_response.get("Items", [])
                all_templates.extend(public_templates)
            except ClientError as e:
                logger.error(json.dumps({"event": "scan_public_templates_error", "error": str(e)}))
                # Continue with just user templates if public scan fails
                pass

        # Group by template_id and keep only latest version
        template_dict = {}
        for template in all_templates:
            template_id = template["template_id"]
            version = template.get("version", 1)

            if template_id not in template_dict or version > template_dict[template_id].get(
                "version", 0
            ):
                template_dict[template_id] = template

        # Format response (remove full template_definition for list view)
        templates = []
        for template in template_dict.values():
            templates.append(
                {
                    "template_id": template["template_id"],
                    "version": template.get("version", 1),
                    "name": template["name"],
                    "user_id": template["user_id"],
                    "is_public": template.get("is_public", False),
                    "is_owner": template["user_id"] == user_id,
                    "schema_requirements": template.get("schema_requirements", []),
                    "created_at": template["created_at"],
                    "description": template.get("description", ""),
                    "step_count": len(template.get("template_definition", {}).get("steps", [])),
                }
            )

        # Sort by created_at (newest first)
        templates.sort(key=lambda x: x["created_at"], reverse=True)

        logger.info(
            json.dumps(
                {"event": "list_templates_success", "user_id": user_id, "count": len(templates)}
            )
        )

        return success_response(200, {"templates": templates, "count": len(templates)}, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
