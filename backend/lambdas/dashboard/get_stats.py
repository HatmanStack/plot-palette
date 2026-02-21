"""
Plot Palette - Dashboard Statistics Lambda Handler

GET /dashboard/{job_id} endpoint that aggregates real-time job progress,
cost breakdown, budget tracking, and performance metrics.
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
cost_tracking_table = dynamodb.Table(
    os.environ.get("COST_TRACKING_TABLE_NAME", "plot-palette-CostTracking")
)


def calculate_cost_breakdown(job_id: str) -> dict[str, float]:
    """
    Query CostTracking table and calculate total costs by category.

    Args:
        job_id: Job identifier

    Returns:
        Dict with bedrock, fargate, s3, and total costs
    """
    try:
        response = cost_tracking_table.query(KeyConditionExpression=Key("job_id").eq(job_id))

        bedrock_cost = 0.0
        fargate_cost = 0.0
        s3_cost = 0.0

        for item in response.get("Items", []):
            estimated_cost = item.get("estimated_cost", 0.0)

            # If estimated_cost is a dict with breakdown
            if isinstance(estimated_cost, dict):
                bedrock_cost += float(estimated_cost.get("bedrock", 0.0))
                fargate_cost += float(estimated_cost.get("fargate", 0.0))
                s3_cost += float(estimated_cost.get("s3", 0.0))
            else:
                # If it's a single number, assume it's mostly Bedrock cost
                bedrock_cost += float(estimated_cost)

        return {
            "bedrock": round(bedrock_cost, 4),
            "fargate": round(fargate_cost, 4),
            "s3": round(s3_cost, 4),
            "total": round(bedrock_cost + fargate_cost + s3_cost, 4),
        }

    except ClientError as e:
        logger.error(
            json.dumps({"event": "cost_calculation_error", "job_id": job_id, "error": str(e)})
        )
        # Return zeros if cost tracking fails
        return {"bedrock": 0.0, "fargate": 0.0, "s3": 0.0, "total": 0.0}


def estimate_completion(
    records_generated: int, target_records: int, started_at: str | None
) -> str | None:
    """
    Estimate job completion time based on current generation rate.

    Args:
        records_generated: Number of records generated so far
        target_records: Total target records
        started_at: Job start timestamp (ISO format)

    Returns:
        Estimated completion time (ISO format) or None if cannot estimate
    """
    if not started_at or records_generated == 0 or target_records == 0:
        return None

    try:
        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        elapsed = (now - start_time).total_seconds()

        if elapsed <= 0:
            return None

        rate = records_generated / elapsed  # records per second
        remaining = target_records - records_generated

        if rate > 0 and remaining > 0:
            eta_seconds = remaining / rate
            eta = now + timedelta(seconds=eta_seconds)
            return eta.isoformat().replace("+00:00", "Z")

    except (ValueError, TypeError) as e:
        logger.warning(json.dumps({"event": "eta_calculation_error", "error": str(e)}))

    return None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /dashboard/{job_id} endpoint.

    Returns comprehensive dashboard statistics including progress,
    cost breakdown, budget tracking, and timing information.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response with dashboard stats
    """
    try:
        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        # Extract job ID from path parameters
        job_id = event["pathParameters"]["job_id"]

        logger.info(
            json.dumps({"event": "get_stats_request", "user_id": user_id, "job_id": job_id})
        )

        # Get job from DynamoDB
        try:
            response = jobs_table.get_item(Key={"job_id": job_id})
        except ClientError as e:
            logger.error(json.dumps({"event": "get_job_error", "error": str(e)}))
            return error_response(500, "Error retrieving job")

        if "Item" not in response:
            return error_response(404, "Job not found")

        job = response["Item"]

        # Authorization check
        if job["user_id"] != user_id:
            logger.warning(
                json.dumps(
                    {"event": "unauthorized_stats_access", "user_id": user_id, "job_id": job_id}
                )
            )
            return error_response(403, "Access denied - you do not own this job")

        # Calculate cost breakdown
        cost_breakdown = calculate_cost_breakdown(job_id)

        # Extract job details
        target_records = job.get("config", {}).get("num_records", 0)
        records_generated = job.get("records_generated", 0)

        # Calculate progress percentage
        progress_pct = 0.0
        if target_records > 0:
            progress_pct = (records_generated / target_records) * 100

        # Estimate completion time for running jobs
        eta = None
        if job["status"] == "RUNNING":
            eta = estimate_completion(records_generated, target_records, job.get("started_at"))

        # Parse budget limit (might be stored as string)
        budget_limit = job.get("budget_limit", 0)
        if isinstance(budget_limit, str):
            budget_limit = float(budget_limit)

        # Build statistics response
        stats = {
            "job_id": job_id,
            "status": job["status"],
            "progress": {
                "records_generated": records_generated,
                "target_records": target_records,
                "percentage": round(progress_pct, 2),
            },
            "cost": cost_breakdown,
            "budget": {
                "limit": budget_limit,
                "used": cost_breakdown["total"],
                "remaining": round(budget_limit - cost_breakdown["total"], 4),
                "percentage_used": round(
                    (cost_breakdown["total"] / budget_limit * 100) if budget_limit > 0 else 0, 2
                ),
            },
            "timing": {
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "updated_at": job.get("updated_at"),
                "estimated_completion": eta,
            },
            "tokens_used": job.get("tokens_used", 0),
            "template_id": job.get("config", {}).get("template_id"),
        }

        logger.info(
            json.dumps(
                {
                    "event": "get_stats_success",
                    "job_id": job_id,
                    "status": job["status"],
                    "progress": progress_pct,
                }
            )
        )

        return success_response(200, stats, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
