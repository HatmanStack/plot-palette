"""
Plot Palette - Delete Job Lambda Handler

DELETE /jobs/{job_id} endpoint that cancels or deletes jobs based on their status.
- QUEUED: Remove from queue and mark as CANCELLED
- RUNNING: Signal ECS task to stop and mark as CANCELLED
- COMPLETED/FAILED/CANCELLED: Delete job record and S3 data
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
from aws_clients import get_dynamodb_resource, get_ecs_client, get_s3_client, get_sfn_client

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
cost_tracking_table = dynamodb.Table(
    os.environ.get("COST_TRACKING_TABLE_NAME", "plot-palette-CostTracking")
)

ecs_client = get_ecs_client()
s3_client = get_s3_client()
sfn_client = get_sfn_client()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for DELETE /jobs/{job_id} endpoint.

    Cancels running jobs or deletes completed jobs based on status.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        set_correlation_id(extract_request_id(event))

        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        # Extract job ID from path parameters
        job_id = event["pathParameters"]["job_id"]

        logger.info(
            json.dumps({"event": "delete_job_request", "user_id": user_id, "job_id": job_id})
        )

        # Get current job
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
                    {"event": "unauthorized_delete_attempt", "user_id": user_id, "job_id": job_id}
                )
            )
            return error_response(403, "Access denied - you do not own this job")

        status = job["status"]
        bucket = os.environ.get("BUCKET_NAME", "")
        if not bucket:
            logger.error("BUCKET_NAME environment variable is not set")
            return error_response(500, "Server configuration error: storage not configured")

        if status == "QUEUED":
            # Stop Step Functions execution if present
            execution_arn = job.get("execution_arn")
            if execution_arn:
                try:
                    sfn_client.stop_execution(
                        executionArn=execution_arn,
                        cause="User cancelled job",
                    )
                    logger.info(
                        json.dumps(
                            {
                                "event": "sfn_execution_stopped",
                                "job_id": job_id,
                                "execution_arn": execution_arn,
                            }
                        )
                    )
                except ClientError as e:
                    logger.error(
                        json.dumps(
                            {
                                "event": "sfn_stop_error",
                                "error": str(e),
                            }
                        )
                    )

            # Update job status to CANCELLED
            try:
                jobs_table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET #status = :status, updated_at = :now",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "CANCELLED",
                        ":now": datetime.now(UTC).isoformat(),
                    },
                )
            except ClientError as e:
                logger.error(json.dumps({"event": "job_update_error", "error": str(e)}))
                return error_response(500, "Error cancelling job")

            message = "Job cancelled successfully"

        elif status == "RUNNING":
            # Stop execution — prefer SFN, fall back to ECS for legacy jobs
            execution_arn = job.get("execution_arn")
            if execution_arn:
                try:
                    sfn_client.stop_execution(
                        executionArn=execution_arn,
                        cause="User cancelled job",
                    )
                    logger.info(
                        json.dumps(
                            {
                                "event": "sfn_execution_stopped",
                                "job_id": job_id,
                                "execution_arn": execution_arn,
                            }
                        )
                    )
                except ClientError as e:
                    logger.error(
                        json.dumps(
                            {
                                "event": "sfn_stop_error",
                                "error": str(e),
                            }
                        )
                    )
            else:
                # Legacy path: stop ECS task directly
                task_arn = job.get("task_arn")
                cluster_name = os.environ.get("ECS_CLUSTER_NAME", "plot-palette-cluster")
                if task_arn:
                    try:
                        ecs_client.stop_task(
                            cluster=cluster_name,
                            task=task_arn,
                            reason="User cancelled job",
                        )
                        logger.info(
                            json.dumps(
                                {
                                    "event": "ecs_task_stopped",
                                    "job_id": job_id,
                                    "task_arn": task_arn,
                                }
                            )
                        )
                    except ClientError as e:
                        logger.error(
                            json.dumps(
                                {
                                    "event": "ecs_stop_error",
                                    "error": str(e),
                                }
                            )
                        )

            # Update status to CANCELLED in Jobs table
            try:
                jobs_table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET #status = :status, updated_at = :now",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "CANCELLED",
                        ":now": datetime.now(UTC).isoformat(),
                    },
                )
            except ClientError as e:
                logger.error(json.dumps({"event": "job_update_error", "error": str(e)}))
                return error_response(500, "Error cancelling job")

            message = "Job cancellation requested - task will stop shortly"

        else:  # COMPLETED, FAILED, CANCELLED, BUDGET_EXCEEDED
            # Delete S3 data
            delete_s3_job_data(s3_client, bucket, job_id, logger)

            # Delete cost tracking records
            delete_cost_tracking_records(cost_tracking_table, job_id, logger)

            # Delete job record (only if still in terminal status)
            try:
                jobs_table.delete_item(
                    Key={"job_id": job_id},
                    ConditionExpression="#status IN (:completed, :failed, :cancelled, :budget)",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":completed": "COMPLETED",
                        ":failed": "FAILED",
                        ":cancelled": "CANCELLED",
                        ":budget": "BUDGET_EXCEEDED",
                    },
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return error_response(409, "Job status changed during deletion, please retry")
                logger.error(json.dumps({"event": "job_delete_error", "error": str(e)}))
                return error_response(500, "Error deleting job")

            message = "Job deleted successfully"

        logger.info(
            json.dumps(
                {
                    "event": "delete_job_success",
                    "job_id": job_id,
                    "previous_status": status,
                    "action": message,
                }
            )
        )

        return success_response(200, {"message": message, "job_id": job_id})

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
