"""
Plot Palette - Get Batch Lambda Handler

GET /jobs/batches/{batch_id} endpoint that returns batch details
including job-level summaries.
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
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource

dynamodb = get_dynamodb_resource()
batches_table = dynamodb.Table(os.environ.get("BATCHES_TABLE_NAME", "plot-palette-Batches"))
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /jobs/batches/{batch_id} endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        batch_id = event["pathParameters"]["batch_id"]

        logger.info(
            json.dumps({"event": "get_batch_request", "user_id": user_id, "batch_id": batch_id})
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

        # Authorization check
        if batch["user_id"] != user_id:
            return error_response(403, "Access denied - you do not own this batch")

        # Fetch job details using batch_get_item for efficiency
        job_ids = batch.get("job_ids", [])
        jobs = []
        jobs_load_error = False

        if job_ids:
            table_name = os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs")
            # batch_get_item supports max 100 keys, we have max 20
            try:
                keys = [{"job_id": jid} for jid in job_ids]
                batch_response = dynamodb.batch_get_item(
                    RequestItems={table_name: {"Keys": keys}}
                )
                raw_jobs = batch_response.get("Responses", {}).get(table_name, [])
                # Retry unprocessed keys once
                unprocessed = batch_response.get("UnprocessedKeys", {})
                if unprocessed:
                    retry_response = dynamodb.batch_get_item(RequestItems=unprocessed)
                    raw_jobs.extend(
                        retry_response.get("Responses", {}).get(table_name, [])
                    )
                for job in raw_jobs:
                    jobs.append({
                        "job_id": job["job_id"],
                        "status": job["status"],
                        "records_generated": job.get("records_generated", 0),
                        "cost_estimate": float(job.get("cost_estimate", 0)),
                        "budget_limit": float(job.get("budget_limit", 0)),
                        "created_at": job.get("created_at", ""),
                        "updated_at": job.get("updated_at", ""),
                    })
            except ClientError as e:
                logger.error(json.dumps({"event": "batch_get_jobs_error", "error": str(e)}))
                jobs_load_error = True

        # Compute live batch status from job statuses (only when jobs loaded)
        if not jobs_load_error:
            terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXCEEDED"}
            completed_count = sum(1 for j in jobs if j["status"] == "COMPLETED")
            failed_count = sum(1 for j in jobs if j["status"] in {"FAILED", "CANCELLED", "BUDGET_EXCEEDED"})
            total_cost = sum(j.get("cost_estimate", 0) for j in jobs)
            all_terminal = all(j["status"] in terminal_statuses for j in jobs) if jobs else False

            if all_terminal and jobs:
                computed_status = "COMPLETED" if failed_count == 0 else "PARTIAL_FAILURE"
            else:
                computed_status = batch["status"]

            # Update batch record if status changed
            if (
                computed_status != batch["status"]
                or completed_count != int(batch.get("completed_jobs", 0))
            ):
                try:
                    batches_table.update_item(
                        Key={"batch_id": batch_id},
                        UpdateExpression="SET #s = :status, completed_jobs = :comp, failed_jobs = :fail, total_cost = :cost, updated_at = :now",
                        ExpressionAttributeNames={"#s": "status"},
                        ExpressionAttributeValues={
                            ":status": computed_status,
                            ":comp": completed_count,
                            ":fail": failed_count,
                            ":cost": round(total_cost, 4),
                            ":now": datetime.now(UTC).isoformat(),
                        },
                    )
                except ClientError:
                    pass  # Best effort — don't fail the read
        else:
            # Preserve existing batch values when jobs failed to load
            computed_status = batch["status"]
            completed_count = int(batch.get("completed_jobs", 0))
            failed_count = int(batch.get("failed_jobs", 0))
            total_cost = float(batch.get("total_cost", 0))

        result = {
            "batch_id": batch["batch_id"],
            "name": batch["name"],
            "status": computed_status,
            "created_at": batch["created_at"],
            "updated_at": batch["updated_at"],
            "total_jobs": batch.get("total_jobs", 0),
            "completed_jobs": completed_count,
            "failed_jobs": failed_count,
            "template_id": batch["template_id"],
            "template_version": batch.get("template_version", 1),
            "sweep_config": batch.get("sweep_config", {}),
            "total_cost": round(total_cost, 4),
            "jobs": jobs,
            "jobs_load_error": jobs_load_error,
        }

        return success_response(200, result, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
