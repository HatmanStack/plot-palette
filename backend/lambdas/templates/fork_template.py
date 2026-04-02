"""
Plot Palette - Fork Template Lambda Handler

POST /templates/{template_id}/fork endpoint that copies a public
template into the authenticated user's collection as a new template.
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402
from lambda_responses import error_response, success_response  # noqa: E402
from utils import (  # noqa: E402
    extract_request_id,
    generate_template_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
)

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource  # noqa: E402

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for POST /templates/{template_id}/fork endpoint.

    Copies a public template (or user's own template) into the
    authenticated user's collection with a new template_id and version 1.

    Request body (optional):
        name: custom name for the forked template
    """
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        source_template_id = event["pathParameters"]["template_id"]

        logger.info(
            json.dumps(
                {
                    "event": "fork_template_request",
                    "user_id": user_id,
                    "source_template_id": source_template_id,
                }
            )
        )

        # Parse optional body for name override
        body: dict[str, Any] = {}
        if event.get("body"):
            try:
                body = json.loads(event["body"])
            except json.JSONDecodeError:
                pass

        # Fetch the source template (latest version)
        try:
            response = templates_table.query(
                KeyConditionExpression=Key("template_id").eq(source_template_id),
                ScanIndexForward=False,  # Descending by version (sort key)
                Limit=1,
            )
        except ClientError as e:
            logger.error(json.dumps({"event": "query_source_error", "error": str(e)}))
            return error_response(500, "Error fetching source template")

        items = response.get("Items", [])
        if not items:
            return error_response(404, "Template not found")

        source = items[0]

        # Authorization: must be public or owned by the user
        if (
            str(source.get("is_public", "false")).lower() != "true"
            and source.get("user_id") != user_id
        ):
            logger.warning(
                json.dumps(
                    {
                        "event": "fork_unauthorized",
                        "user_id": user_id,
                        "source_template_id": source_template_id,
                    }
                )
            )
            return error_response(403, "Cannot fork a private template you do not own")

        # Generate new template
        new_template_id = generate_template_id()
        original_name = source.get("name", "Untitled")
        fork_name = body.get("name") or f"{original_name} (fork)"
        now = datetime.now(UTC).isoformat()

        new_template = {
            "template_id": new_template_id,
            "version": 1,
            "name": fork_name,
            "user_id": user_id,
            "template_definition": source.get("template_definition", {}),
            "schema_requirements": source.get("schema_requirements", []),
            "description": source.get("description", ""),
            "is_public": "false",
            "created_at": now,
        }

        # Write to DynamoDB
        try:
            templates_table.put_item(
                Item=new_template,
                ConditionExpression="attribute_not_exists(template_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return error_response(409, "Fork conflict, please retry")
            logger.error(json.dumps({"event": "fork_write_error", "error": str(e)}))
            return error_response(500, "Error creating forked template")

        logger.info(
            json.dumps(
                {
                    "event": "template_forked",
                    "source_template_id": source_template_id,
                    "new_template_id": new_template_id,
                    "user_id": user_id,
                }
            )
        )

        return success_response(
            201,
            {
                "template_id": new_template_id,
                "name": fork_name,
                "version": 1,
                "message": "Template forked successfully",
            },
        )

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
