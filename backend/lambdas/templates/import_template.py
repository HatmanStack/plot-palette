"""
Plot Palette - Import Template Lambda Handler

POST /templates/import endpoint that imports templates from YAML files.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from botocore.exceptions import ClientError

try:
    import yaml
except ImportError:
    # YAML will be available via Lambda layer
    yaml = None

from utils import setup_logger, generate_template_id
from template_filters import validate_template_syntax

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
templates_table = dynamodb.Table(os.environ.get('TEMPLATES_TABLE_NAME', 'plot-palette-Templates'))


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
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        logger.info(json.dumps({
            "event": "import_template_request",
            "user_id": user_id
        }))

        # Parse request body
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        yaml_content = body.get('yaml_content')
        if not yaml_content:
            return error_response(400, "Missing required field: yaml_content")

        # Parse YAML
        try:
            template_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {str(e)}")
            return error_response(400, f"Invalid YAML: {str(e)}")

        # Validate structure - ensure it's a dict
        if not isinstance(template_data, dict):
            return error_response(400, "Invalid template format: YAML must contain a mapping/object")

        if 'template' not in template_data:
            return error_response(400, "Invalid template format: missing 'template' key")

        template = template_data['template']

        # Validate template is also a dict
        if not isinstance(template, dict):
            return error_response(400, "Invalid template format: 'template' must be a mapping/object")

        # Validate required fields
        if 'name' not in template:
            return error_response(400, "Invalid template: missing 'name'")

        if 'steps' not in template or not template['steps']:
            return error_response(400, "Invalid template: missing or empty 'steps'")

        # Validate template syntax
        template_def = {'steps': template['steps']}
        valid, error_msg = validate_template_syntax(template_def)
        if not valid:
            return error_response(400, f"Template validation failed: {error_msg}")

        # Extract schema requirements from template
        import jinja2
        import jinja2.meta

        env = jinja2.Environment()
        all_variables = set()

        for step in template['steps']:
            prompt = step.get('prompt', '')
            ast = env.parse(prompt)
            variables = jinja2.meta.find_undeclared_variables(ast)
            all_variables.update(variables)

        # Filter out built-in variables
        built_ins = {'steps', 'loop', 'range', 'dict', 'list'}
        schema_reqs = sorted([v for v in all_variables if v not in built_ins])

        # Generate new template ID
        new_template_id = generate_template_id()
        now = datetime.utcnow().isoformat()

        # Create template record
        new_template = {
            'template_id': new_template_id,
            'version': 1,
            'name': template.get('name', 'Imported Template'),
            'description': template.get('description', 'Imported from YAML'),
            'category': template.get('category', 'general'),
            'user_id': user_id,
            'template_definition': {'steps': template['steps']},
            'schema_requirements': schema_reqs,
            'created_at': now,
            'is_public': False  # Imported templates are private by default
        }

        # Insert into DynamoDB
        try:
            templates_table.put_item(Item=new_template)
        except ClientError as e:
            logger.error(f"DynamoDB error: {str(e)}")
            return error_response(500, "Error creating template")

        logger.info(json.dumps({
            "event": "template_imported",
            "template_id": new_template_id,
            "user_id": user_id,
            "name": new_template['name']
        }))

        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "template_id": new_template_id,
                "version": 1,
                "name": new_template['name'],
                "schema_requirements": schema_reqs,
                "message": "Template imported successfully"
            })
        }

    except KeyError as e:
        logger.error(f"Missing field: {str(e)}", exc_info=True)
        return error_response(400, f"Missing required field: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response(500, "Internal server error")
