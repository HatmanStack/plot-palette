"""
Plot Palette - Create Template Lambda Handler

POST /templates endpoint that creates new prompt templates with Jinja2
validation and automatic schema extraction.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import jinja2
import jinja2.meta
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from utils import generate_template_id, sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get('TEMPLATES_TABLE_NAME', 'plot-palette-Templates'))


def extract_schema_requirements(template_definition: Dict[str, Any]) -> List[str]:
    """
    Extract all {{ variable }} references from Jinja2 template.

    Args:
        template_definition: Template definition dictionary with steps

    Returns:
        List[str]: Sorted list of unique variable references

    Raises:
        ValueError: If template syntax is invalid
    """
    env = jinja2.Environment()
    all_variables = set()

    try:
        # Extract variables from all steps
        for step in template_definition.get('steps', []):
            prompt = step.get('prompt', '')
            ast = env.parse(prompt)
            variables = jinja2.meta.find_undeclared_variables(ast)
            all_variables.update(variables)

        # Filter out built-in variables like 'steps'
        built_ins = {'steps', 'loop', 'range', 'dict', 'list'}
        schema_vars = [v for v in all_variables if v not in built_ins]

        return sorted(schema_vars)

    except jinja2.TemplateSyntaxError as e:
        raise ValueError(f"Invalid template syntax: {str(e)}") from e


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Generate error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"error": message})
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for POST /templates endpoint.

    Creates a new prompt template with Jinja2 validation and schema extraction.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with template_id
    """
    try:
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        logger.info(json.dumps({
            "event": "create_template_request",
            "user_id": user_id
        }))

        # Parse request body
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Check idempotency token
        idempotency_token = body.get('idempotency_token')
        if idempotency_token:
            try:
                existing = templates_table.query(
                    IndexName='user-id-index',
                    KeyConditionExpression=Key('user_id').eq(user_id),
                    FilterExpression=Attr('idempotency_token').eq(idempotency_token),
                    Limit=1,
                )
                if existing.get('Items'):
                    item = existing['Items'][0]
                    logger.info(json.dumps({
                        "event": "idempotent_template_returned",
                        "template_id": item['template_id'],
                        "idempotency_token": idempotency_token,
                    }))
                    return {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json",
                            "Access-Control-Allow-Origin": "*",
                        },
                        "body": json.dumps({
                            "template_id": item['template_id'],
                            "version": item.get('version', 1),
                            "message": "Existing template returned (idempotent)",
                        }),
                    }
            except ClientError as e:
                logger.warning(json.dumps({
                    "event": "idempotency_check_failed",
                    "error": str(e),
                }))

        # Validate required fields
        if 'name' not in body:
            return error_response(400, "Missing required field: name")

        if 'template_definition' not in body:
            return error_response(400, "Missing required field: template_definition")

        template_def = body['template_definition']

        # Validate template has steps
        if 'steps' not in template_def or not template_def['steps']:
            return error_response(400, "Template must have at least one step")

        # Validate Jinja2 syntax and extract schema
        try:
            # First validate template syntax (including filters, conditionals, loops)
            from template_filters import validate_template_syntax
            valid, error_msg = validate_template_syntax(template_def)
            if not valid:
                return error_response(400, error_msg)

            schema_reqs = extract_schema_requirements(template_def)
        except ValueError as e:
            return error_response(400, str(e))

        # Generate template ID
        template_id = generate_template_id()
        now = datetime.utcnow().isoformat()

        # Create template record
        template = {
            'template_id': template_id,
            'version': 1,
            'name': body['name'],
            'user_id': user_id,
            'template_definition': template_def,
            'schema_requirements': schema_reqs,
            'created_at': now,
            'is_public': body.get('is_public', False),
            'description': body.get('description', '')
        }

        # Insert into Templates table
        try:
            if idempotency_token:
                template['idempotency_token'] = idempotency_token
            templates_table.put_item(
                Item=template,
                ConditionExpression='attribute_not_exists(template_id)',
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(json.dumps({
                    "event": "template_id_conflict",
                    "template_id": template_id,
                }))
                return error_response(409, "Template creation conflict, please retry")
            logger.error(json.dumps({
                "event": "template_insert_error",
                "error": str(e)
            }))
            return error_response(500, "Error creating template")

        logger.info(json.dumps({
            "event": "template_created",
            "template_id": template_id,
            "user_id": user_id,
            "name": body['name'],
            "schema_requirements": schema_reqs
        }))

        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "template_id": template_id,
                "version": 1,
                "schema_requirements": schema_reqs,
                "message": "Template created successfully"
            })
        }

    except KeyError as e:
        logger.error(json.dumps({
            "event": "missing_field_error",
            "error": str(e)
        }))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({
            "event": "unexpected_error",
            "error": str(e)
        }), exc_info=True)
        return error_response(500, "Internal server error")
