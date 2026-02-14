"""
Plot Palette - List Jobs Lambda Handler

GET /jobs endpoint that lists all jobs for the authenticated user with
pagination and filtering support.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /jobs endpoint.

    Lists all jobs for the authenticated user with optional pagination
    and status filtering.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with list of jobs
    """
    try:
        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        logger.info(json.dumps({"event": "list_jobs_request", "user_id": user_id}))

        # Parse query parameters
        params = event.get("queryStringParameters") or {}

        # Validate and parse limit parameter
        try:
            limit = int(params.get("limit", 20))
            if limit < 1:
                limit = 20
            elif limit > 100:
                limit = 100
        except (ValueError, TypeError):
            return error_response(
                400, "Invalid limit parameter - must be a number between 1 and 100"
            )

        status_filter = params.get("status")

        # Build query parameters
        query_params = {
            "IndexName": "user-id-index",
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "Limit": limit,
            "ScanIndexForward": False,  # Descending order (newest first)
        }

        # Add status filter if provided (use Attr for non-key attributes)
        if status_filter:
            query_params["FilterExpression"] = Attr("status").eq(status_filter)

        # Handle pagination
        if "last_key" in params:
            try:
                query_params["ExclusiveStartKey"] = json.loads(params["last_key"])
            except json.JSONDecodeError:
                return error_response(400, "Invalid last_key parameter")

        # Query DynamoDB
        try:
            response = jobs_table.query(**query_params)
        except ClientError as e:
            logger.error(json.dumps({"event": "query_error", "error": str(e)}))
            return error_response(500, "Error querying jobs")

        # Format response with summary data
        jobs = []
        for item in response.get("Items", []):
            jobs.append(
                {
                    "job_id": item["job_id"],
                    "status": item["status"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "records_generated": item.get("records_generated", 0),
                    "cost_estimate": float(item.get("cost_estimate", 0.0))
                    if isinstance(item.get("cost_estimate"), str)
                    else item.get("cost_estimate", 0.0),
                    "budget_limit": float(item["budget_limit"])
                    if isinstance(item.get("budget_limit"), str)
                    else item.get("budget_limit", 0.0),
                }
            )

        result = {"jobs": jobs}

        # Add pagination token if there are more results
        if "LastEvaluatedKey" in response:
            result["last_key"] = json.dumps(response["LastEvaluatedKey"])
            result["has_more"] = True
        else:
            result["has_more"] = False

        logger.info(
            json.dumps({"event": "list_jobs_success", "user_id": user_id, "count": len(jobs)})
        )

        return success_response(200, result, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
