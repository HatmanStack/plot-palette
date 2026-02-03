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
from datetime import datetime
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from utils import setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
jobs_table = dynamodb.Table(os.environ.get('JOBS_TABLE_NAME', 'plot-palette-Jobs'))
queue_table = dynamodb.Table(os.environ.get('QUEUE_TABLE_NAME', 'plot-palette-Queue'))
cost_tracking_table = dynamodb.Table(os.environ.get('COST_TRACKING_TABLE_NAME', 'plot-palette-CostTracking'))

ecs_client = boto3.client('ecs')
s3_client = boto3.client('s3')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Generate error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"error": message})
    }


def delete_s3_job_data(bucket: str, job_id: str) -> None:
    """
    Delete all S3 data for a job.

    Args:
        bucket: S3 bucket name
        job_id: Job identifier
    """
    prefix = f"jobs/{job_id}/"
    paginator = s3_client.get_paginator('list_objects_v2')

    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' in page:
                objects = [{'Key': obj['Key']} for obj in page['Contents']]
                if objects:
                    s3_client.delete_objects(
                        Bucket=bucket,
                        Delete={'Objects': objects}
                    )
                    logger.info(json.dumps({
                        "event": "s3_objects_deleted",
                        "job_id": job_id,
                        "count": len(objects)
                    }))
    except ClientError as e:
        logger.error(json.dumps({
            "event": "s3_delete_error",
            "job_id": job_id,
            "error": str(e)
        }))
        # Don't fail the entire operation if S3 delete fails
        pass


def delete_cost_tracking_records(job_id: str) -> None:
    """
    Delete all cost tracking records for a job (paginated).

    Args:
        job_id: Job identifier
    """
    try:
        deleted_count = 0
        last_evaluated_key = None

        # Paginate through all cost tracking records
        while True:
            query_kwargs = {
                'KeyConditionExpression': Key('job_id').eq(job_id)
            }
            if last_evaluated_key:
                query_kwargs['ExclusiveStartKey'] = last_evaluated_key

            response = cost_tracking_table.query(**query_kwargs)

            # Delete each record in this page
            for item in response.get('Items', []):
                cost_tracking_table.delete_item(
                    Key={
                        'job_id': job_id,
                        'timestamp': item['timestamp']
                    }
                )
                deleted_count += 1

            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break

        logger.info(json.dumps({
            "event": "cost_tracking_deleted",
            "job_id": job_id,
            "count": deleted_count
        }))

    except ClientError as e:
        logger.error(json.dumps({
            "event": "cost_tracking_delete_error",
            "job_id": job_id,
            "error": str(e)
        }))
        # Don't fail the entire operation


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
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
        # Extract user ID from JWT claims
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        # Extract job ID from path parameters
        job_id = event['pathParameters']['job_id']

        logger.info(json.dumps({
            "event": "delete_job_request",
            "user_id": user_id,
            "job_id": job_id
        }))

        # Get current job
        try:
            response = jobs_table.get_item(Key={'job_id': job_id})
        except ClientError as e:
            logger.error(json.dumps({
                "event": "get_job_error",
                "error": str(e)
            }))
            return error_response(500, "Error retrieving job")

        if 'Item' not in response:
            return error_response(404, "Job not found")

        job = response['Item']

        # Authorization check
        if job['user_id'] != user_id:
            logger.warning(json.dumps({
                "event": "unauthorized_delete_attempt",
                "user_id": user_id,
                "job_id": job_id
            }))
            return error_response(403, "Access denied - you do not own this job")

        status = job['status']
        bucket = os.environ.get('BUCKET_NAME', f'plot-palette-{os.environ.get("AWS_ACCOUNT_ID", "")}')

        if status == 'QUEUED':
            # Remove from queue
            try:
                queue_table.delete_item(
                    Key={
                        'status': 'QUEUED',
                        'job_id_timestamp': f"{job_id}#{job['created_at']}"
                    }
                )
            except ClientError as e:
                logger.error(json.dumps({
                    "event": "queue_delete_error",
                    "error": str(e)
                }))

            # Update job status to CANCELLED
            try:
                jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression='SET #status = :status, updated_at = :now',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'CANCELLED',
                        ':now': datetime.utcnow().isoformat()
                    }
                )
            except ClientError as e:
                logger.error(json.dumps({
                    "event": "job_update_error",
                    "error": str(e)
                }))
                return error_response(500, "Error cancelling job")

            message = "Job cancelled successfully"

        elif status == 'RUNNING':
            # Stop ECS task if it exists
            task_arn = job.get('task_arn')
            cluster_name = os.environ.get('ECS_CLUSTER_NAME', 'plot-palette-cluster')

            if task_arn:
                try:
                    ecs_client.stop_task(
                        cluster=cluster_name,
                        task=task_arn,
                        reason='User cancelled job'
                    )
                    logger.info(json.dumps({
                        "event": "ecs_task_stopped",
                        "job_id": job_id,
                        "task_arn": task_arn
                    }))
                except ClientError as e:
                    logger.error(json.dumps({
                        "event": "ecs_stop_error",
                        "error": str(e)
                    }))
                    # Continue even if ECS stop fails

            # Update status to CANCELLED in Jobs table
            try:
                jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression='SET #status = :status, updated_at = :now',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'CANCELLED',
                        ':now': datetime.utcnow().isoformat()
                    }
                )
            except ClientError as e:
                logger.error(json.dumps({
                    "event": "job_update_error",
                    "error": str(e)
                }))
                return error_response(500, "Error cancelling job")

            # Update Queue table - move from RUNNING to CANCELLED
            try:
                # First try to delete from RUNNING queue
                queue_table.delete_item(
                    Key={
                        'status': 'RUNNING',
                        'job_id_timestamp': f"{job_id}#{job.get('started_at', job['created_at'])}"
                    }
                )
                # Add to CANCELLED queue for tracking
                queue_table.put_item(Item={
                    'status': 'CANCELLED',
                    'job_id_timestamp': f"{job_id}#{datetime.utcnow().isoformat()}",
                    'job_id': job_id,
                    'cancelled_at': datetime.utcnow().isoformat()
                })
            except ClientError as e:
                logger.error(json.dumps({
                    "event": "queue_update_error",
                    "error": str(e)
                }))
                # Don't fail the cancellation if queue update fails

            message = "Job cancellation requested - task will stop shortly"

        else:  # COMPLETED, FAILED, CANCELLED, BUDGET_EXCEEDED
            # Delete S3 data
            delete_s3_job_data(bucket, job_id)

            # Delete cost tracking records
            delete_cost_tracking_records(job_id)

            # Delete job record
            try:
                jobs_table.delete_item(Key={'job_id': job_id})
            except ClientError as e:
                logger.error(json.dumps({
                    "event": "job_delete_error",
                    "error": str(e)
                }))
                return error_response(500, "Error deleting job")

            message = "Job deleted successfully"

        logger.info(json.dumps({
            "event": "delete_job_success",
            "job_id": job_id,
            "previous_status": status,
            "action": message
        }))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "message": message,
                "job_id": job_id
            })
        }

    except KeyError as e:
        logger.error(json.dumps({
            "event": "missing_field_error",
            "error": str(e)
        }))
        return error_response(400, f"Missing required field: {str(e)}")

    except Exception as e:
        logger.error(json.dumps({
            "event": "unexpected_error",
            "error": str(e)
        }), exc_info=True)
        return error_response(500, "Internal server error")
