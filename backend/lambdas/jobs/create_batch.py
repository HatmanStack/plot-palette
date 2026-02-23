"""
Plot Palette - Create Batch Lambda Handler

POST /jobs/batch endpoint that creates multiple generation jobs
from a single configuration with parameter sweep support.
"""

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from constants import MAX_BATCH_SIZE, MODEL_TIERS, BatchStatus, ExportFormat, JobStatus
from lambda_responses import error_response, success_response
from models import BatchConfig, JobConfig
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_sfn_client

dynamodb = get_dynamodb_resource()
sfn_client = get_sfn_client()

jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))
batches_table = dynamodb.Table(os.environ.get("BATCHES_TABLE_NAME", "plot-palette-Batches"))

ALLOWED_SWEEP_KEYS = {"model_tier", "seed_data_path", "num_records"}


def validate_batch_request(body: dict[str, Any]) -> tuple[bool, str]:
    """Validate batch creation request body."""
    required_fields = ["name", "template_id", "template_version", "base_config", "sweep"]
    for field in required_fields:
        if field not in body:
            return False, f"Missing required field: {field}"

    base_config = body["base_config"]
    for field in ["budget_limit", "num_records", "output_format"]:
        if field not in base_config:
            return False, f"Missing required field in base_config: {field}"

    budget_limit = base_config["budget_limit"]
    if not isinstance(budget_limit, (int, float)) or budget_limit <= 0 or budget_limit > 1000:
        return False, "budget_limit must be between 0 and 1000 USD"

    output_format = base_config["output_format"]
    if output_format not in [fmt.value for fmt in ExportFormat]:
        return (
            False,
            f"output_format must be one of: {', '.join(fmt.value for fmt in ExportFormat)}",
        )

    num_records = base_config["num_records"]
    if not isinstance(num_records, int) or num_records <= 0 or num_records > 1_000_000:
        return False, "num_records must be between 1 and 1,000,000"

    sweep = body["sweep"]
    if not isinstance(sweep, dict) or len(sweep) == 0:
        return False, "sweep must be a non-empty object"

    if len(sweep) > 1:
        return False, "Only a single sweep dimension is allowed per batch"

    sweep_key = next(iter(sweep))
    if sweep_key not in ALLOWED_SWEEP_KEYS:
        return False, f"Invalid sweep key: {sweep_key}. Allowed: {', '.join(ALLOWED_SWEEP_KEYS)}"

    sweep_values = sweep[sweep_key]
    if not isinstance(sweep_values, list) or len(sweep_values) < 1:
        return False, "Sweep values must be a non-empty list"

    if len(sweep_values) > MAX_BATCH_SIZE:
        return (
            False,
            f"Sweep produces {len(sweep_values)} jobs, exceeds MAX_BATCH_SIZE ({MAX_BATCH_SIZE})",
        )

    # Validate sweep values by type
    if sweep_key == "model_tier":
        valid_tiers = set(MODEL_TIERS.keys())
        for tier in sweep_values:
            if tier not in valid_tiers:
                return False, f"Invalid model_tier: {tier}"

    if sweep_key == "num_records":
        for n in sweep_values:
            if not isinstance(n, int) or n <= 0 or n > 1_000_000:
                return False, "All num_records sweep values must be between 1 and 1,000,000"

    return True, ""


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /jobs/batch endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        logger.info(json.dumps({"event": "create_batch_request", "user_id": user_id}))

        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Validate request
        is_valid, error_msg = validate_batch_request(body)
        if not is_valid:
            return error_response(400, error_msg)

        # Validate template exists
        template_id = body["template_id"]
        template_version = body["template_version"]
        try:
            template_response = templates_table.get_item(
                Key={"template_id": template_id, "version": template_version}
            )
            if "Item" not in template_response:
                return error_response(404, "Template not found")
        except ClientError as e:
            logger.error(json.dumps({"event": "template_lookup_error", "error": str(e)}))
            return error_response(500, "Error validating template")

        # Seed data path: from body-level or base_config
        seed_data_path = body.get("seed_data_path", body["base_config"].get("seed_data_path", ""))

        # Build individual jobs from sweep
        sweep = body["sweep"]
        sweep_key = next(iter(sweep))
        sweep_values = sweep[sweep_key]

        batch_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        base_config = body["base_config"]

        successful_job_ids = []
        failed_jobs_info = []

        for sweep_value in sweep_values:
            job_id = str(uuid.uuid4())

            # Build job config by merging base with sweep override
            job_config = {
                "template_id": template_id,
                "template_version": template_version,
                "budget_limit": base_config["budget_limit"],
                "num_records": base_config["num_records"],
                "output_format": base_config["output_format"],
                "seed_data_path": seed_data_path,
                "batch_id": batch_id,
            }

            # Apply sweep override
            if sweep_key == "seed_data_path":
                job_config["seed_data_path"] = sweep_value
            elif sweep_key == "model_tier":
                job_config["model_tier"] = sweep_value
            elif sweep_key == "num_records":
                job_config["num_records"] = sweep_value

            # Create JobConfig model
            job = JobConfig(
                job_id=job_id,
                user_id=user_id,
                status=JobStatus.QUEUED,
                created_at=now,
                updated_at=now,
                config=job_config,
                budget_limit=job_config["budget_limit"],
            )

            try:
                # Store job
                jobs_table.put_item(
                    Item=job.to_table_item(),
                    ConditionExpression="attribute_not_exists(job_id)",
                )

                # Start SFN execution
                state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "")
                execution_response = sfn_client.start_execution(
                    stateMachineArn=state_machine_arn,
                    name=f"job-{job_id}",
                    input=json.dumps({"job_id": job_id, "user_id": user_id, "retry_count": 0}),
                )

                # Update job with execution ARN
                jobs_table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET execution_arn = :arn",
                    ExpressionAttributeValues={":arn": execution_response["executionArn"]},
                )

                successful_job_ids.append(job_id)

            except Exception as e:
                sanitized = sanitize_error_message(str(e))
                logger.error(
                    json.dumps(
                        {
                            "event": "batch_job_creation_failed",
                            "batch_id": batch_id,
                            "job_id": job_id,
                            "sweep_value": str(sweep_value),
                            "error": sanitized,
                        }
                    )
                )
                failed_jobs_info.append({"sweep_value": str(sweep_value), "error": sanitized})
                # Mark job as failed if it was stored
                try:
                    jobs_table.update_item(
                        Key={"job_id": job_id},
                        UpdateExpression="SET #s = :failed, updated_at = :now",
                        ExpressionAttributeNames={"#s": "status"},
                        ExpressionAttributeValues={
                            ":failed": "FAILED",
                            ":now": datetime.now(UTC).isoformat(),
                        },
                    )
                except Exception:
                    pass

        # Determine batch status
        if not successful_job_ids:
            return error_response(500, "All jobs in batch failed to create")

        batch_status = BatchStatus.RUNNING
        if failed_jobs_info:
            batch_status = BatchStatus.PARTIAL_FAILURE

        # Store batch record
        batch = BatchConfig(
            batch_id=batch_id,
            user_id=user_id,
            name=body["name"],
            status=batch_status,
            created_at=now,
            updated_at=now,
            job_ids=successful_job_ids,
            total_jobs=len(successful_job_ids),
            completed_jobs=0,
            failed_jobs=len(failed_jobs_info),
            template_id=template_id,
            template_version=template_version,
            sweep_config=sweep,
            total_cost=0.0,
        )

        try:
            batches_table.put_item(Item=batch.to_table_item())
        except ClientError as e:
            logger.error(json.dumps({"event": "batch_store_error", "error": str(e)}))
            return error_response(500, "Failed to store batch record")

        logger.info(
            json.dumps(
                {
                    "event": "batch_created",
                    "batch_id": batch_id,
                    "user_id": user_id,
                    "total_jobs": len(successful_job_ids),
                    "failed_jobs": len(failed_jobs_info),
                }
            )
        )

        response_body: dict[str, Any] = {
            "batch_id": batch_id,
            "job_count": len(successful_job_ids),
            "job_ids": successful_job_ids,
        }
        if failed_jobs_info:
            response_body["failed_jobs"] = failed_jobs_info

        return success_response(201, response_body)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
