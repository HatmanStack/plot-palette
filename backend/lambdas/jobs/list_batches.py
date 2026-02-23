"""
Plot Palette - List Batches Lambda Handler

GET /jobs/batches endpoint that lists all batches for the authenticated user.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
batches_table = dynamodb.Table(os.environ.get("BATCHES_TABLE_NAME", "plot-palette-Batches"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /jobs/batches endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        logger.info(json.dumps({"event": "list_batches_request", "user_id": user_id}))

        params = event.get("queryStringParameters") or {}

        try:
            limit = min(max(int(params.get("limit", 20)), 1), 100)
        except (ValueError, TypeError):
            return error_response(400, "Invalid limit parameter")

        query_params: dict[str, Any] = {
            "IndexName": "user-id-index",
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "Limit": limit,
            "ScanIndexForward": False,
        }

        if "last_key" in params:
            try:
                cursor = json.loads(params["last_key"])
                if not isinstance(cursor, dict) or "batch_id" not in cursor:
                    return error_response(400, "Invalid pagination cursor structure")
                query_params["ExclusiveStartKey"] = cursor
            except json.JSONDecodeError:
                return error_response(400, "Invalid last_key parameter")

        try:
            response = batches_table.query(**query_params)
        except ClientError as e:
            logger.error(json.dumps({"event": "query_error", "error": str(e)}))
            return error_response(500, "Error querying batches")

        batches = []
        for item in response.get("Items", []):
            batches.append(
                {
                    "batch_id": item["batch_id"],
                    "name": item["name"],
                    "status": item["status"],
                    "total_jobs": item.get("total_jobs", 0),
                    "completed_jobs": item.get("completed_jobs", 0),
                    "failed_jobs": item.get("failed_jobs", 0),
                    "created_at": item["created_at"],
                    "total_cost": float(item.get("total_cost", 0)),
                }
            )

        result: dict[str, Any] = {"batches": batches}

        if "LastEvaluatedKey" in response:
            result["last_key"] = json.dumps(response["LastEvaluatedKey"])
            result["has_more"] = True
        else:
            result["has_more"] = False

        return success_response(200, result, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
