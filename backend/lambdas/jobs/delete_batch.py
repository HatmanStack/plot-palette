"""
Plot Palette - Delete Batch Lambda Handler

DELETE /jobs/batches/{batch_id} endpoint that cancels running jobs
and deletes the batch record.
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import (
    delete_cost_tracking_records,
    delete_s3_job_data,
    extract_request_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
)

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_s3_client, get_sfn_client

dynamodb = get_dynamodb_resource()
sfn_client = get_sfn_client()
s3_client = get_s3_client()
batches_table = dynamodb.Table(os.environ.get("BATCHES_TABLE_NAME", "plot-palette-Batches"))
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
cost_tracking_table = dynamodb.Table(
    os.environ.get("COST_TRACKING_TABLE_NAME", "plot-palette-CostTracking")
)

CANCELLABLE_STATUSES = {"QUEUED", "RUNNING"}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXCEEDED"}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for DELETE /jobs/batches/{batch_id} endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        batch_id = event["pathParameters"]["batch_id"]

        logger.info(
            json.dumps({"event": "delete_batch_request", "user_id": user_id, "batch_id": batch_id})
        )

        # Fetch batch
        try:
            response = batches_table.get_item(Key={"batch_id": batch_id})
        except ClientError as e:
            logger.error(json.dumps({"event": "get_batch_error", "error": str(e)}))
            return error_response(500, "Error retrieving batch")

        if "Item" not in response:
            return error_response(404, "Batch not found")

        batch = response["Item"]

        if batch["user_id"] != user_id:
            return error_response(403, "Access denied - you do not own this batch")

        jobs_cancelled = 0
        jobs_deleted = 0

        # Process each job in the batch
        for job_id in batch.get("job_ids", []):
            try:
                job_response = jobs_table.get_item(Key={"job_id": job_id})
                if "Item" not in job_response:
                    continue

                job = job_response["Item"]
                status = job["status"]

                if status in CANCELLABLE_STATUSES:
                    # Cancel running/queued job
                    execution_arn = job.get("execution_arn")
                    if execution_arn:
                        try:
                            sfn_client.stop_execution(
                                executionArn=execution_arn,
                                cause="Batch deleted by user",
                            )
                        except ClientError:
                            pass

                    jobs_table.update_item(
                        Key={"job_id": job_id},
                        UpdateExpression="SET #s = :status, updated_at = :now",
                        ExpressionAttributeNames={"#s": "status"},
                        ExpressionAttributeValues={
                            ":status": "CANCELLED",
                            ":now": datetime.now(UTC).isoformat(),
                        },
                    )
                    jobs_cancelled += 1

                elif status in TERMINAL_STATUSES:
                    # Clean up S3 data and cost tracking records
                    bucket = os.environ.get("BUCKET_NAME", "")
                    if bucket:
                        delete_s3_job_data(s3_client, bucket, job_id, logger)
                    delete_cost_tracking_records(cost_tracking_table, job_id, logger)
                    # Delete terminal job record
                    jobs_table.delete_item(Key={"job_id": job_id})
                    jobs_deleted += 1

            except ClientError as e:
                logger.error(
                    json.dumps(
                        {"event": "batch_job_cleanup_error", "job_id": job_id, "error": str(e)}
                    )
                )

        # Delete batch record
        try:
            batches_table.delete_item(Key={"batch_id": batch_id})
        except ClientError as e:
            logger.error(json.dumps({"event": "batch_delete_error", "error": str(e)}))
            return error_response(500, "Error deleting batch record")

        logger.info(
            json.dumps(
                {
                    "event": "batch_deleted",
                    "batch_id": batch_id,
                    "jobs_cancelled": jobs_cancelled,
                    "jobs_deleted": jobs_deleted,
                }
            )
        )

        return success_response(
            200,
            {
                "message": "Batch deleted successfully",
                "batch_id": batch_id,
                "jobs_cancelled": jobs_cancelled,
                "jobs_deleted": jobs_deleted,
            },
        )

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
