"""
Plot Palette - Validate Seed Data Lambda Handler

POST /seed-data/validate endpoint that validates uploaded seed data
against a template's schema requirements.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from botocore.exceptions import ClientError
from utils import sanitize_error_message, setup_logger, validate_seed_data

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
s3_client = boto3.client('s3')
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
    Lambda handler for POST /seed-data/validate endpoint.

    Validates seed data file against template schema requirements.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with validation result
    """
    try:
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        logger.info(json.dumps({
            "event": "validate_seed_data_request",
            "user_id": user_id
        }))

        # Parse request body
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Validate required fields
        s3_key = body.get('s3_key')
        template_id = body.get('template_id')

        if not s3_key:
            return error_response(400, "Missing required field: s3_key")

        if not template_id:
            return error_response(400, "Missing required field: template_id")

        # Get template to retrieve schema requirements
        # Normalize template_version to int
        template_version_raw = body.get('template_version', 1)
        try:
            template_version = int(template_version_raw)
            if template_version < 1:
                return error_response(400, "template_version must be a positive integer")
        except (ValueError, TypeError):
            return error_response(400, f"Invalid template_version: must be a positive integer, got {template_version_raw}")

        try:
            template_response = templates_table.get_item(
                Key={
                    'template_id': template_id,
                    'version': template_version
                }
            )

            if 'Item' not in template_response:
                return error_response(404, "Template not found")

            template = template_response['Item']

        except ClientError as e:
            logger.error(json.dumps({
                "event": "template_lookup_error",
                "error": str(e)
            }))
            return error_response(500, "Error retrieving template")

        schema_requirements = template.get('schema_requirements', [])

        # If no schema requirements, validation passes
        if not schema_requirements:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "valid": True,
                    "message": "Template has no schema requirements"
                })
            }

        # Download seed data sample (first 1MB to avoid memory issues)
        bucket = os.environ.get('BUCKET_NAME')

        if not bucket:
            return error_response(500, "Server configuration error")

        try:
            # Use Range header to download only first 1MB
            response = s3_client.get_object(
                Bucket=bucket,
                Key=s3_key,
                Range='bytes=0-1048576'
            )

            data_bytes = response['Body'].read()
            data_sample = json.loads(data_bytes)

        except s3_client.exceptions.NoSuchKey:
            return error_response(404, "Seed data file not found")

        except json.JSONDecodeError as e:
            return error_response(400, f"Invalid JSON in seed data file: {sanitize_error_message(str(e))}")

        except ClientError as e:
            logger.error(json.dumps({
                "event": "s3_download_error",
                "error": str(e)
            }))
            return error_response(500, "Error downloading seed data")

        # Validate schema
        is_valid, error_msg = validate_seed_data(data_sample, schema_requirements)

        if not is_valid:
            logger.info(json.dumps({
                "event": "validation_failed",
                "user_id": user_id,
                "s3_key": s3_key,
                "template_id": template_id,
                "error": error_msg
            }))

            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "valid": False,
                    "error": error_msg,
                    "schema_requirements": schema_requirements
                })
            }

        logger.info(json.dumps({
            "event": "validation_success",
            "user_id": user_id,
            "s3_key": s3_key,
            "template_id": template_id
        }))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "valid": True,
                "message": "Seed data is valid for template",
                "schema_requirements_checked": schema_requirements
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
