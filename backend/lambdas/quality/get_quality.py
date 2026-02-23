"""
Plot Palette - Get Quality Metrics Lambda Handler

GET /jobs/{job_id}/quality endpoint that returns quality scoring results
for a completed job.
"""

import json
import os
import sys
from decimal import Decimal
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from aws_clients import get_dynamodb_resource  # noqa: E402
from lambda_responses import error_response, success_response  # noqa: E402
from utils import extract_request_id, set_correlation_id, setup_logger  # noqa: E402

logger = setup_logger(__name__)

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
quality_table = dynamodb.Table(
    os.environ.get("QUALITY_METRICS_TABLE_NAME", "plot-palette-QualityMetrics")
)


def _decimal_to_float(obj: Any) -> Any:
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /jobs/{job_id}/quality endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        job_id = event.get("pathParameters", {}).get("job_id", "")

        if not job_id:
            return error_response(400, "Missing job_id")

        # Verify job exists and ownership
        job_response = jobs_table.get_item(Key={"job_id": job_id})
        job = job_response.get("Item")
        if not job:
            return error_response(404, "Job not found")

        if job.get("user_id") != user_id:
            return error_response(403, "Not authorized to view this job's quality metrics")

        # Fetch quality metrics
        quality_response = quality_table.get_item(Key={"job_id": job_id})
        metrics = quality_response.get("Item")
        if not metrics:
            return error_response(404, "Quality metrics not found for this job")

        # Convert Decimals and return
        result = _decimal_to_float(metrics)
        # Remove TTL from response
        result.pop("ttl", None)

        return success_response(200, result)

    except KeyError as e:
        return error_response(400, f"Missing required field: {str(e)}")

    except Exception as e:
        logger.error(json.dumps({"event": "get_quality_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
