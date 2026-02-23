"""
Plot Palette - Stream Job Progress Lambda Handler

GET /jobs/{job_id}/stream endpoint that returns Server-Sent Events (SSE)
formatted response with current job progress. EventSource auto-reconnects
to provide near-real-time updates.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from lambda_responses import CORS_HEADERS, error_response
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "BUDGET_EXCEEDED", "CANCELLED"}


def _build_sse_response(event_type: str | None, data: dict[str, Any]) -> dict[str, Any]:
    """Build an SSE-formatted API Gateway response."""
    body_lines = []
    if event_type:
        body_lines.append(f"event: {event_type}")
    body_lines.append(f"data: {json.dumps(data, default=str)}")
    body_lines.append("")
    body_lines.append("")

    headers = CORS_HEADERS.copy()
    headers["Content-Type"] = "text/event-stream"
    headers["Cache-Control"] = "no-cache"
    headers["Connection"] = "keep-alive"

    return {
        "statusCode": 200,
        "headers": headers,
        "body": "\n".join(body_lines),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /jobs/{job_id}/stream endpoint.

    Returns SSE-formatted response with current job state.
    For terminal states, includes event: complete signal.
    """
    try:
        set_correlation_id(extract_request_id(event))

        try:
            user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        except (KeyError, TypeError):
            return error_response(401, "Authentication required")

        job_id = event["pathParameters"]["job_id"]

        logger.info(
            json.dumps(
                {
                    "event": "stream_progress_request",
                    "user_id": user_id,
                    "job_id": job_id,
                }
            )
        )

        # Fetch job from DynamoDB
        response = jobs_table.get_item(Key={"job_id": job_id})

        if "Item" not in response:
            return error_response(404, "Job not found")

        job = response["Item"]

        # Authorization check - ensure user owns this job
        if job.get("user_id") != user_id:
            logger.warning(
                json.dumps(
                    {
                        "event": "unauthorized_stream_attempt",
                        "user_id": user_id,
                        "job_id": job_id,
                    }
                )
            )
            return error_response(403, "Access denied - you do not own this job")

        # Build progress data
        cost_estimate = job.get("cost_estimate", 0)
        if hasattr(cost_estimate, "__float__"):
            cost_estimate = float(cost_estimate)

        budget_limit = job.get("budget_limit", 0)
        if hasattr(budget_limit, "__float__"):
            budget_limit = float(budget_limit)

        progress_data = {
            "job_id": job_id,
            "status": job.get("status", "UNKNOWN"),
            "records_generated": int(job.get("records_generated", 0)),
            "tokens_used": int(job.get("tokens_used", 0)),
            "cost_estimate": cost_estimate,
            "budget_limit": budget_limit,
            "updated_at": str(job.get("updated_at", "")),
        }

        status = job.get("status", "")

        if status in TERMINAL_STATUSES:
            return _build_sse_response("complete", progress_data)
        else:
            return _build_sse_response(None, progress_data)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
