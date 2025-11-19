"""
Plot Palette - Delete Template Lambda Handler

DELETE /templates/{template_id} endpoint that deletes all versions of a template
if it is not currently in use by any jobs.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

from utils import setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
templates_table = dynamodb.Table(os.environ.get('TEMPLATES_TABLE_NAME', 'plot-palette-Templates'))
jobs_table = dynamodb.Table(os.environ.get('JOBS_TABLE_NAME', 'plot-palette-Jobs'))


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


def template_in_use(template_id: str) -> tuple[bool, int]:
    """
    Check if template is used by any jobs.

    Returns:
        tuple[bool, int]: (is_in_use, job_count)
    """
    try:
        # Scan jobs table for this template_id
        # Note: This could be slow for large tables; consider adding a GSI on template_id
        response = jobs_table.scan(
            FilterExpression=Attr('config.template_id').eq(template_id),
            Limit=1  # Just need to know if any exist
        )

        job_count = len(response.get('Items', []))
        return job_count > 0, job_count

    except ClientError as e:
        logger.error(json.dumps({
            "event": "check_template_usage_error",
            "error": str(e)
        }))
        # Err on the side of caution
        return True, 0


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for DELETE /templates/{template_id} endpoint.

    Deletes all versions of a template if not in use by any jobs.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        # Extract template ID from path parameters
        template_id = event['pathParameters']['template_id']

        logger.info(json.dumps({
            "event": "delete_template_request",
            "user_id": user_id,
            "template_id": template_id
        }))

        # Get all versions to verify ownership
        try:
            response = templates_table.query(
                KeyConditionExpression=Key('template_id').eq(template_id)
            )

            if not response.get('Items'):
                return error_response(404, "Template not found")

            templates = response['Items']

            # Check ownership (all versions should have same owner)
            if templates[0]['user_id'] != user_id:
                return error_response(403, "Access denied - you do not own this template")

        except ClientError as e:
            logger.error(json.dumps({
                "event": "get_template_error",
                "error": str(e)
            }))
            return error_response(500, "Error retrieving template")

        # Check if template is in use
        in_use, job_count = template_in_use(template_id)

        if in_use:
            return error_response(
                409,
                f"Cannot delete template - it is currently used by {job_count} job(s)"
            )

        # Delete all versions
        try:
            for template in templates:
                templates_table.delete_item(
                    Key={
                        'template_id': template_id,
                        'version': template['version']
                    }
                )

        except ClientError as e:
            logger.error(json.dumps({
                "event": "template_delete_error",
                "error": str(e)
            }))
            return error_response(500, "Error deleting template")

        logger.info(json.dumps({
            "event": "template_deleted",
            "template_id": template_id,
            "versions_deleted": len(templates)
        }))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "message": "Template deleted successfully",
                "template_id": template_id,
                "versions_deleted": len(templates)
            })
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
