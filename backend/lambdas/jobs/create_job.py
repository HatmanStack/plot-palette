"""
Plot Palette - Create Job Lambda Handler

POST /jobs endpoint that creates new generation jobs with configuration
validation, budget limits, and Step Functions orchestration.
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

import uuid

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from constants import ExportFormat, JobStatus
from lambda_responses import error_response, success_response
from models import JobConfig
from utils import (
    extract_request_id,
    generate_job_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
)

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_sfn_client

dynamodb = get_dynamodb_resource()
sfn_client = get_sfn_client()

jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))


def validate_job_config(config: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate job configuration parameters.

    Args:
        config: Job configuration dictionary

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    required_fields = [
        "template_id",
        "seed_data_path",
        "budget_limit",
        "output_format",
        "num_records",
    ]

    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"

    # Validate budget_limit
    budget_limit = config["budget_limit"]
    if not isinstance(budget_limit, (int, float)) or budget_limit <= 0 or budget_limit > 1000:
        return False, "budget_limit must be between 0 and 1000 USD"

    # Validate output_format
    output_format = config["output_format"]
    if output_format not in [fmt.value for fmt in ExportFormat]:
        return (
            False,
            f"output_format must be one of: {', '.join([fmt.value for fmt in ExportFormat])}",
        )

    # Validate num_records
    num_records = config["num_records"]
    if not isinstance(num_records, int) or num_records <= 0 or num_records > 1_000_000:
        return False, "num_records must be between 1 and 1,000,000"

    return True, ""


def start_job_execution(job_id: str) -> str:
    """
    Start Step Functions execution for job processing.

    Args:
        job_id: Job ID to process

    Returns:
        str: Execution ARN

    Raises:
        ClientError: If execution cannot be started
    """
    state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "")

    if not state_machine_arn:
        raise ValueError("STATE_MACHINE_ARN environment variable not set")

    try:
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"job-{job_id}",
            input=json.dumps({"job_id": job_id, "retry_count": 0}),
        )

        execution_arn = response["executionArn"]
        logger.info(
            json.dumps(
                {
                    "event": "sfn_execution_started",
                    "job_id": job_id,
                    "execution_arn": execution_arn,
                }
            )
        )
        return execution_arn

    except ClientError as e:
        logger.error(
            json.dumps(
                {
                    "event": "sfn_execution_start_error",
                    "job_id": job_id,
                    "error": str(e),
                }
            )
        )
        raise


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for POST /jobs endpoint.

    Creates a new generation job with validated configuration, inserts it
    into the Jobs table, and starts a Step Functions execution.

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

        logger.info(json.dumps({"event": "create_job_request", "user_id": user_id}))

        # Parse request body
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Check idempotency token (generate server-side if client doesn't provide one)
        idempotency_token = body.get("idempotency_token") or str(uuid.uuid4())
        if body.get("idempotency_token"):
            try:
                existing = jobs_table.query(
                    IndexName="user-id-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                    FilterExpression=Attr("idempotency_token").eq(idempotency_token),
                )
                if existing.get("Items"):
                    item = existing["Items"][0]
                    logger.info(
                        json.dumps(
                            {
                                "event": "idempotent_job_returned",
                                "job_id": item["job_id"],
                                "idempotency_token": idempotency_token,
                            }
                        )
                    )
                    return success_response(
                        200,
                        {
                            "job_id": item["job_id"],
                            "status": item["status"],
                            "created_at": item.get("created_at", ""),
                            "message": "Existing job returned (idempotent)",
                        },
                    )
            except ClientError as e:
                logger.warning(
                    json.dumps(
                        {
                            "event": "idempotency_check_failed",
                            "error": str(e),
                        }
                    )
                )

        # Validate configuration
        is_valid, error_msg = validate_job_config(body)
        if not is_valid:
            return error_response(400, error_msg)

        # Validate template exists
        template_id = body["template_id"]
        template_version_raw = body.get("template_version", 1)
        try:
            template_version = int(template_version_raw)
            if template_version < 1:
                return error_response(400, "template_version must be a positive integer")
        except (ValueError, TypeError):
            return error_response(400, "template_version must be a positive integer")

        try:
            template_response = templates_table.get_item(
                Key={"template_id": template_id, "version": template_version}
            )

            if "Item" not in template_response:
                return error_response(404, "Template not found")

        except ClientError as e:
            logger.error(json.dumps({"event": "template_lookup_error", "error": str(e)}))
            return error_response(500, "Error validating template")

        # Generate job ID
        job_id = generate_job_id()
        now = datetime.now(UTC)

        # Create job record
        job = JobConfig(
            job_id=job_id,
            user_id=user_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            config=body,
            budget_limit=body["budget_limit"],
            tokens_used=0,
            records_generated=0,
            cost_estimate=0.0,
        )

        # Insert into Jobs table using high-level Table format
        try:
            job_item = job.to_table_item()
            if idempotency_token:
                job_item["idempotency_token"] = idempotency_token
            jobs_table.put_item(
                Item=job_item,
                ConditionExpression="attribute_not_exists(job_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    json.dumps(
                        {
                            "event": "job_id_conflict",
                            "job_id": job_id,
                        }
                    )
                )
                return error_response(409, "Job creation conflict, please retry")
            logger.error(json.dumps({"event": "job_insert_error", "error": str(e)}))
            return error_response(500, "Error creating job")

        logger.info(
            json.dumps(
                {
                    "event": "job_created",
                    "job_id": job_id,
                    "user_id": user_id,
                    "budget_limit": body["budget_limit"],
                    "num_records": body["num_records"],
                }
            )
        )

        # Start Step Functions execution for the job
        try:
            execution_arn = start_job_execution(job_id)
            # Store execution ARN on job record
            jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET execution_arn = :arn",
                ExpressionAttributeValues={":arn": execution_arn},
            )
        except Exception as e:
            logger.error(
                json.dumps(
                    {
                        "event": "sfn_execution_start_failed",
                        "job_id": job_id,
                        "error": str(e),
                    }
                )
            )
            # Mark job as failed so it doesn't stay QUEUED with no execution
            try:
                jobs_table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET #s = :failed, updated_at = :now, error_message = :err",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":failed": "FAILED",
                        ":now": datetime.now(UTC).isoformat(),
                        ":err": "Failed to start job execution",
                    },
                )
            except ClientError:
                logger.error(
                    json.dumps(
                        {
                            "event": "sfn_failure_status_update_failed",
                            "job_id": job_id,
                        }
                    )
                )
            return error_response(500, "Job created but failed to start execution")

        return success_response(
            201,
            {
                "job_id": job_id,
                "status": "QUEUED",
                "created_at": now.isoformat(),
                "message": "Job created successfully",
            },
        )

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
