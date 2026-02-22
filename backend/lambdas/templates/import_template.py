"""
Plot Palette - Import Template Lambda Handler

POST /templates/import endpoint that imports templates from YAML files.
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

try:
    import yaml
except ImportError:
    # YAML will be available via Lambda layer
    yaml = None

from lambda_responses import error_response, success_response
from template_filters import validate_template_syntax
from utils import generate_template_id, sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for POST /templates/import endpoint.

    Imports a template from YAML content.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with new template_id
    """
    try:
        # Check YAML library availability
        if yaml is None:
            logger.error("PyYAML not available")
            return error_response(500, "YAML import not available")

        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        logger.info(json.dumps({"event": "import_template_request", "user_id": user_id}))

        # Parse request body
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Check idempotency token
        idempotency_token = body.get("idempotency_token")
        if idempotency_token:
            try:
                existing = templates_table.query(
                    IndexName="user-id-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                    FilterExpression=Attr("idempotency_token").eq(idempotency_token),
                )
                if existing.get("Items"):
                    item = existing["Items"][0]
                    logger.info(
                        json.dumps(
                            {
                                "event": "idempotent_import_returned",
                                "template_id": item["template_id"],
                                "idempotency_token": idempotency_token,
                            }
                        )
                    )
                    return success_response(
                        200,
                        {
                            "template_id": item["template_id"],
                            "version": item.get("version", 1),
                            "name": item.get("name", ""),
                            "message": "Existing template returned (idempotent)",
                        },
                    )
            except ClientError as e:
                logger.warning(
                    json.dumps(
                        {
                            "event": "idempotency_check_failed",
                            "error": str(e),
                        }
                    )
                )

        yaml_content = body.get("yaml_content")
        if not yaml_content:
            return error_response(400, "Missing required field: yaml_content")

        # Parse YAML
        try:
            template_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {str(e)}")
            return error_response(400, f"Invalid YAML: {sanitize_error_message(str(e))}")

        # Validate structure - ensure it's a dict
        if not isinstance(template_data, dict):
            return error_response(
                400, "Invalid template format: YAML must contain a mapping/object"
            )

        if "template" not in template_data:
            return error_response(400, "Invalid template format: missing 'template' key")

        template = template_data["template"]

        # Validate template is also a dict
        if not isinstance(template, dict):
            return error_response(
                400, "Invalid template format: 'template' must be a mapping/object"
            )

        # Validate required fields
        if "name" not in template:
            return error_response(400, "Invalid template: missing 'name'")

        if "steps" not in template or not template["steps"]:
            return error_response(400, "Invalid template: missing or empty 'steps'")

        # Validate template syntax
        template_def = {"steps": template["steps"]}
        valid, error_msg = validate_template_syntax(template_def)
        if not valid:
            return error_response(400, f"Template validation failed: {error_msg}")

        # Extract schema requirements from template
        import jinja2
        import jinja2.meta

        env = jinja2.Environment(autoescape=True)
        all_variables = set()

        for step in template["steps"]:
            prompt = step.get("prompt", "")
            ast = env.parse(prompt)
            variables = jinja2.meta.find_undeclared_variables(ast)
            all_variables.update(variables)

        # Filter out built-in variables
        built_ins = {"steps", "loop", "range", "dict", "list"}
        schema_reqs = sorted([v for v in all_variables if v not in built_ins])

        # Generate new template ID
        new_template_id = generate_template_id()
        now = datetime.now(UTC).isoformat()

        # Create template record
        new_template = {
            "template_id": new_template_id,
            "version": 1,
            "name": template.get("name", "Imported Template"),
            "description": template.get("description", "Imported from YAML"),
            "category": template.get("category", "general"),
            "user_id": user_id,
            "template_definition": {"steps": template["steps"]},
            "schema_requirements": schema_reqs,
            "created_at": now,
            "is_public": False,  # Imported templates are private by default
        }

        # Insert into DynamoDB
        try:
            if idempotency_token:
                new_template["idempotency_token"] = idempotency_token
            templates_table.put_item(
                Item=new_template,
                ConditionExpression="attribute_not_exists(template_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    json.dumps(
                        {
                            "event": "template_id_conflict",
                            "template_id": new_template_id,
                        }
                    )
                )
                return error_response(409, "Template creation conflict, please retry")
            logger.error(f"DynamoDB error: {str(e)}")
            return error_response(500, "Error creating template")

        logger.info(
            json.dumps(
                {
                    "event": "template_imported",
                    "template_id": new_template_id,
                    "user_id": user_id,
                    "name": new_template["name"],
                }
            )
        )

        return success_response(
            201,
            {
                "template_id": new_template_id,
                "version": 1,
                "name": new_template["name"],
                "schema_requirements": schema_reqs,
                "message": "Template imported successfully",
            },
        )

    except KeyError as e:
        logger.error(f"Missing field: {str(e)}", exc_info=True)
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response(500, "Internal server error")
