"""
Plot Palette - Get Job Lambda Handler

GET /jobs/{job_id} endpoint that retrieves full details for a specific job.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get('JOBS_TABLE_NAME', 'plot-palette-Jobs'))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /jobs/{job_id} endpoint.

    Retrieves full details for a specific job, including configuration
    and progress information.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with job details
    """
    try:
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        # Extract job ID from path parameters
        job_id = event['pathParameters']['job_id']

        logger.info(json.dumps({
            "event": "get_job_request",
            "user_id": user_id,
            "job_id": job_id
        }))

        # Get job from DynamoDB
        try:
            response = jobs_table.get_item(Key={'job_id': job_id})
        except ClientError as e:
            logger.error(json.dumps({
                "event": "get_item_error",
                "error": str(e)
            }))
            return error_response(500, "Error retrieving job")

        if 'Item' not in response:
            return error_response(404, "Job not found")

        job = response['Item']

        # Authorization check - ensure user owns this job
        if job['user_id'] != user_id:
            logger.warning(json.dumps({
                "event": "unauthorized_access_attempt",
                "user_id": user_id,
                "job_id": job_id,
                "job_owner": job['user_id']
            }))
            return error_response(403, "Access denied - you do not own this job")

        # Convert numeric strings to proper types
        if isinstance(job.get('budget_limit'), str):
            job['budget_limit'] = float(job['budget_limit'])
        if isinstance(job.get('cost_estimate'), str):
            job['cost_estimate'] = float(job['cost_estimate'])

        logger.info(json.dumps({
            "event": "get_job_success",
            "user_id": user_id,
            "job_id": job_id
        }))

        return success_response(200, job, default=str)

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
