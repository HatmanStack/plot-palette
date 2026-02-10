"""
Plot Palette - Create Job Lambda Handler

POST /jobs endpoint that creates new generation jobs with configuration
validation, budget limits, and queue insertion.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from constants import ExportFormat, JobStatus
from lambda_responses import error_response, success_response
from models import JobConfig
from utils import generate_job_id, sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_ecs_client

dynamodb = get_dynamodb_resource()
ecs_client = get_ecs_client()

jobs_table = dynamodb.Table(os.environ.get('JOBS_TABLE_NAME', 'plot-palette-Jobs'))
queue_table = dynamodb.Table(os.environ.get('QUEUE_TABLE_NAME', 'plot-palette-Queue'))
templates_table = dynamodb.Table(os.environ.get('TEMPLATES_TABLE_NAME', 'plot-palette-Templates'))


def validate_job_config(config: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate job configuration parameters.

    Args:
        config: Job configuration dictionary

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    required_fields = ['template_id', 'seed_data_path', 'budget_limit', 'output_format', 'num_records']

    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"

    # Validate budget_limit
    budget_limit = config['budget_limit']
    if not isinstance(budget_limit, (int, float)) or budget_limit <= 0 or budget_limit > 1000:
        return False, "budget_limit must be between 0 and 1000 USD"

    # Validate output_format
    output_format = config['output_format']
    if output_format not in [fmt.value for fmt in ExportFormat]:
        return False, f"output_format must be one of: {', '.join([fmt.value for fmt in ExportFormat])}"

    # Validate num_records
    num_records = config['num_records']
    if not isinstance(num_records, int) or num_records <= 0 or num_records > 1_000_000:
        return False, "num_records must be between 1 and 1,000,000"

    return True, ""


def start_worker_task(job_id: str) -> str:
    """
    Start ECS Fargate task for job processing.

    Args:
        job_id: Job ID to process

    Returns:
        str: Task ARN

    Raises:
        ClientError: If ECS task cannot be started
    """
    cluster_name = os.environ.get('ECS_CLUSTER_NAME', '')
    task_definition = os.environ.get('TASK_DEFINITION_ARN', 'plot-palette-worker')
    subnet_ids_raw = os.environ.get('SUBNET_IDS', '')
    security_group_id = os.environ.get('SECURITY_GROUP_ID', '')

    # Validate required ECS configuration
    if not cluster_name:
        raise ValueError("ECS_CLUSTER_NAME environment variable not set")
    if not subnet_ids_raw:
        raise ValueError("SUBNET_IDS environment variable not set")
    if not security_group_id:
        raise ValueError("SECURITY_GROUP_ID environment variable not set")

    # Parse and filter subnet IDs (remove empty strings)
    subnet_ids = [s.strip() for s in subnet_ids_raw.split(',') if s.strip()]
    if not subnet_ids:
        raise ValueError("SUBNET_IDS contains no valid subnet IDs")

    try:
        response = ecs_client.run_task(
            cluster=cluster_name,
            taskDefinition=task_definition,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': subnet_ids,
                    'securityGroups': [security_group_id],
                    'assignPublicIp': 'ENABLED'
                }
            },
            capacityProviderStrategy=[{
                'capacityProvider': 'FARGATE_SPOT',
                'weight': 1,
                'base': 0
            }],
            enableExecuteCommand=True,  # For debugging
            tags=[
                {'key': 'job-id', 'value': job_id},
                {'key': 'application', 'value': 'plot-palette'}
            ]
        )

        if response['tasks']:
            task_arn = response['tasks'][0]['taskArn']
            logger.info(json.dumps({
                "event": "ecs_task_started",
                "job_id": job_id,
                "task_arn": task_arn
            }))
            return task_arn
        else:
            raise Exception("No tasks returned from run_task")

    except ClientError as e:
        logger.error(json.dumps({
            "event": "ecs_task_start_error",
            "job_id": job_id,
            "error": str(e)
        }))
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for POST /jobs endpoint.

    Creates a new generation job with validated configuration and inserts it
    into the Jobs table and Queue table.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        logger.info(json.dumps({
            "event": "create_job_request",
            "user_id": user_id
        }))

        # Parse request body
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Check idempotency token
        idempotency_token = body.get('idempotency_token')
        if idempotency_token:
            try:
                existing = jobs_table.query(
                    IndexName='user-id-index',
                    KeyConditionExpression=Key('user_id').eq(user_id),
                    FilterExpression=Attr('idempotency_token').eq(idempotency_token),
                    Limit=1,
                )
                if existing.get('Items'):
                    item = existing['Items'][0]
                    logger.info(json.dumps({
                        "event": "idempotent_job_returned",
                        "job_id": item['job_id'],
                        "idempotency_token": idempotency_token,
                    }))
                    return success_response(200, {
                        "job_id": item['job_id'],
                        "status": item['status'],
                        "created_at": item.get('created_at', ''),
                        "message": "Existing job returned (idempotent)",
                    })
            except ClientError as e:
                logger.warning(json.dumps({
                    "event": "idempotency_check_failed",
                    "error": str(e),
                }))

        # Validate configuration
        is_valid, error_msg = validate_job_config(body)
        if not is_valid:
            return error_response(400, error_msg)

        # Validate template exists
        template_id = body['template_id']
        template_version = body.get('template_version', 1)

        try:
            template_response = templates_table.get_item(
                Key={
                    'template_id': template_id,
                    'version': template_version
                }
            )

            if 'Item' not in template_response:
                return error_response(404, "Template not found")

        except ClientError as e:
            logger.error(json.dumps({
                "event": "template_lookup_error",
                "error": str(e)
            }))
            return error_response(500, "Error validating template")

        # Generate job ID
        job_id = generate_job_id()
        now = datetime.utcnow()

        # Create job record
        job = JobConfig(
            job_id=job_id,
            user_id=user_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            config=body,
            budget_limit=body['budget_limit'],
            tokens_used=0,
            records_generated=0,
            cost_estimate=0.0
        )

        # Insert into Jobs table using typed serialization
        try:
            job_item = job.to_dynamodb()
            if idempotency_token:
                job_item['idempotency_token'] = idempotency_token
            jobs_table.put_item(
                Item=job_item,
                ConditionExpression='attribute_not_exists(job_id)',
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(json.dumps({
                    "event": "job_id_conflict",
                    "job_id": job_id,
                }))
                return error_response(409, "Job creation conflict, please retry")
            logger.error(json.dumps({
                "event": "job_insert_error",
                "error": str(e)
            }))
            return error_response(500, "Error creating job")

        # Insert into Queue table
        try:
            queue_table.put_item(
                Item={
                    'status': 'QUEUED',
                    'job_id_timestamp': f"{job_id}#{now.isoformat()}",
                    'job_id': job_id,
                    'priority': body.get('priority', 5),
                    'timestamp': now.isoformat()
                }
            )
        except ClientError as e:
            logger.error(json.dumps({
                "event": "queue_insert_error",
                "error": str(e)
            }))
            # Try to rollback job creation
            try:
                jobs_table.delete_item(Key={'job_id': job_id})
            except ClientError:
                pass
            return error_response(500, "Error queuing job")

        logger.info(json.dumps({
            "event": "job_created",
            "job_id": job_id,
            "user_id": user_id,
            "budget_limit": body['budget_limit'],
            "num_records": body['num_records']
        }))

        # Start ECS worker task to process the job
        try:
            start_worker_task(job_id)
        except Exception as e:
            logger.error(json.dumps({
                "event": "worker_task_start_failed",
                "job_id": job_id,
                "error": str(e)
            }))

        return success_response(201, {
            "job_id": job_id,
            "status": "QUEUED",
            "created_at": now,
            "message": "Job created successfully"
        })

    except KeyError as e:
        logger.error(json.dumps({
            "event": "missing_field_error",
            "error": str(e)
        }))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({
            "event": "unexpected_error",
            "error": str(e)
        }), exc_info=True)
        return error_response(500, "Internal server error")
