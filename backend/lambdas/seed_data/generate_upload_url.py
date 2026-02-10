"""
Plot Palette - Generate Upload URL Lambda Handler

POST /seed-data/upload endpoint that generates presigned S3 URLs for
uploading seed data files.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from constants import PRESIGNED_URL_EXPIRATION
from utils import sanitize_error_message, sanitize_filename, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients (with S3v4 signature for presigned URLs)
s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))


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
    Lambda handler for POST /seed-data/upload endpoint.

    Generates presigned S3 URL for uploading seed data files.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with presigned URL
    """
    try:
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        logger.info(json.dumps({
            "event": "generate_upload_url_request",
            "user_id": user_id
        }))

        # Parse request body
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Validate required fields
        filename = body.get('filename')
        if not filename:
            return error_response(400, "Missing required field: filename")

        # Sanitize filename to prevent path traversal
        try:
            safe_filename = sanitize_filename(filename)
        except ValueError:
            return error_response(400, "Invalid filename")

        content_type = body.get('content_type', 'application/json')

        # Generate S3 key with user isolation
        s3_key = f"seed-data/{user_id}/{safe_filename}"
        bucket = os.environ.get('BUCKET_NAME')

        if not bucket:
            logger.error(json.dumps({
                "event": "missing_bucket_name",
                "error": "BUCKET_NAME environment variable not set"
            }))
            return error_response(500, "Server configuration error")

        # Generate presigned URL
        try:
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket,
                    'Key': s3_key,
                    'ContentType': content_type
                },
                ExpiresIn=PRESIGNED_URL_EXPIRATION
            )
        except ClientError as e:
            logger.error(json.dumps({
                "event": "presigned_url_generation_error",
                "error": str(e)
            }))
            return error_response(500, "Error generating upload URL")

        logger.info(json.dumps({
            "event": "upload_url_generated",
            "user_id": user_id,
            "s3_key": s3_key,
            "expires_in": PRESIGNED_URL_EXPIRATION
        }))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "upload_url": presigned_url,
                "s3_key": s3_key,
                "bucket": bucket,
                "expires_in": PRESIGNED_URL_EXPIRATION,
                "message": f"Upload URL valid for {PRESIGNED_URL_EXPIRATION // 60} minutes"
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
