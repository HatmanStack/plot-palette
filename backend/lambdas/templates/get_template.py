"""
Plot Palette - Get Template Lambda Handler

GET /templates/{template_id} endpoint that retrieves full template details
including the complete template definition.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from botocore.exceptions import ClientError

from utils import setup_logger

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
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        # Extract template ID from path parameters
        template_id = event['pathParameters']['template_id']

        # Parse query parameters
        params = event.get('queryStringParameters') or {}
        version = int(params.get('version', 1))

        logger.info(json.dumps({
            "event": "get_template_request",
            "user_id": user_id,
            "template_id": template_id,
            "version": version
        }))

        # Get template from DynamoDB
        try:
            response = templates_table.get_item(
                Key={
                    'template_id': template_id,
                    'version': version
                }
            )
        except ClientError as e:
            logger.error(json.dumps({
                "event": "get_template_error",
                "error": str(e)
            }))
            return error_response(500, "Error retrieving template")

        if 'Item' not in response:
            return error_response(404, "Template not found")

        template = response['Item']

        # Authorization check - only owner or public templates can be accessed
        if template['user_id'] != user_id and not template.get('is_public', False):
            logger.warning(json.dumps({
                "event": "unauthorized_template_access",
                "user_id": user_id,
                "template_id": template_id,
                "template_owner": template['user_id']
            }))
            return error_response(403, "Access denied - template is private")

        # Add ownership flag
        template['is_owner'] = template['user_id'] == user_id

        logger.info(json.dumps({
            "event": "get_template_success",
            "user_id": user_id,
            "template_id": template_id
        }))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(template, default=str)
        }

    except KeyError as e:
        logger.error(json.dumps({
            "event": "missing_field_error",
            "error": str(e)
        }))
        return error_response(400, f"Missing required field: {str(e)}")

    except Exception as e:
        logger.error(json.dumps({
            "event": "unexpected_error",
            "error": str(e)
        }), exc_info=True)
        return error_response(500, "Internal server error")
