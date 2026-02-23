"""
Plot Palette - Trigger Quality Scoring Lambda Handler

POST /jobs/{job_id}/quality endpoint that triggers asynchronous
quality scoring for a completed job.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from aws_clients import get_lambda_client  # noqa: E402
from lambda_responses import error_response, success_response  # noqa: E402
from utils import (  # noqa: E402
    extract_request_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
)

logger = setup_logger(__name__)

from aws_clients import get_dynamodb_resource  # noqa: E402

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
quality_table = dynamodb.Table(
    os.environ.get("QUALITY_METRICS_TABLE_NAME", "plot-palette-QualityMetrics")
)
lambda_client = get_lambda_client()

SCORE_JOB_FUNCTION_NAME = os.environ.get(
    "SCORE_JOB_FUNCTION_NAME", "plot-palette-score-job"
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /jobs/{job_id}/quality endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        job_id = event.get("pathParameters", {}).get("job_id", "")

        if not job_id:
            return error_response(400, "Missing job_id")

        # Verify job exists, is owned by user, and is COMPLETED
        job_response = jobs_table.get_item(Key={"job_id": job_id})
        job = job_response.get("Item")
        if not job:
            return error_response(404, "Job not found")

        if job.get("user_id") != user_id:
            return error_response(403, "Not authorized to trigger scoring for this job")

        if job.get("status") != "COMPLETED":
            return error_response(400, f"Job must be COMPLETED to score (current: {job.get('status')})")

        # Check if already scored
        quality_response = quality_table.get_item(Key={"job_id": job_id})
        existing = quality_response.get("Item")
        if existing and existing.get("status") == "COMPLETED":
            return error_response(409, "Quality scoring already completed for this job")

        # Parse optional sample_size from body
        sample_size = None
        if event.get("body"):
            try:
                body = json.loads(event["body"])
                sample_size = body.get("sample_size")
            except json.JSONDecodeError:
                pass

        # Invoke score_job Lambda asynchronously
        payload = {"job_id": job_id}
        if sample_size:
            payload["sample_size"] = sample_size

        lambda_client.invoke(
            FunctionName=SCORE_JOB_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps(payload).encode("utf-8"),
        )

        logger.info(
            json.dumps({"event": "scoring_triggered", "job_id": job_id, "user_id": user_id})
        )

        return success_response(202, {
            "message": "Quality scoring started",
            "job_id": job_id,
        })

    except KeyError as e:
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "trigger_scoring_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
