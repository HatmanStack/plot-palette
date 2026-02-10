"""
Plot Palette - Export Template Lambda Handler

GET /templates/{template_id}/export endpoint that exports templates as YAML files.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from botocore.exceptions import ClientError

try:
    import yaml
except ImportError:
    # YAML will be available via Lambda layer
    yaml = None

from utils import sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
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
    Lambda handler for GET /templates/{template_id}/export endpoint.

    Exports a template as a downloadable YAML file.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with YAML content
    """
    try:
        # Check YAML library availability
        if yaml is None:
            logger.error("PyYAML not available")
            return error_response(500, "YAML export not available")

        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
        template_id = event['pathParameters']['template_id']

        logger.info(json.dumps({
            "event": "export_template_request",
            "user_id": user_id,
            "template_id": template_id
        }))

        # Get template from DynamoDB
        try:
            response = templates_table.get_item(
                Key={'template_id': template_id, 'version': 1}
            )
        except ClientError as e:
            logger.error(f"DynamoDB error: {str(e)}")
            return error_response(500, "Error retrieving template")

        if 'Item' not in response:
            return error_response(404, "Template not found")

        template = response['Item']

        # Check ownership or public access
        if template['user_id'] != user_id and not template.get('is_public', False):
            return error_response(403, "Access denied to this template")

        # Build export data structure
        export_data = {
            'template': {
                'id': template_id,
                'name': template['name'],
                'description': template.get('description', ''),
                'category': template.get('category', 'general'),
                'version': template.get('version', 1),
                'schema_requirements': template.get('schema_requirements', []),
                'is_public': template.get('is_public', False),
                'steps': template['template_definition'].get('steps', [])
            }
        }

        # Convert to YAML
        try:
            yaml_content = yaml.dump(
                export_data,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                indent=2
            )
        except Exception as e:
            logger.error(f"YAML serialization error: {str(e)}", exc_info=True)
            return error_response(500, "Error generating YAML")

        # Create safe filename
        safe_name = template_id.replace('/', '-').replace('\\', '-')
        filename = f"{safe_name}.yaml"

        logger.info(json.dumps({
            "event": "template_exported",
            "template_id": template_id,
            "filename": filename
        }))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/x-yaml",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "Content-Disposition"
            },
            "body": yaml_content
        }

    except KeyError as e:
        logger.error(f"Missing field: {str(e)}", exc_info=True)
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response(500, "Internal server error")
