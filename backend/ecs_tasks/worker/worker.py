"""
Plot Palette - ECS Generation Worker

This worker pulls jobs from the DynamoDB queue, generates synthetic data using
AWS Bedrock, and implements checkpoint-based graceful shutdown for Spot interruptions.
"""

import signal
import sys
import logging
import json
import os
import time
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')

# DynamoDB tables
jobs_table = dynamodb.Table(os.environ.get('JOBS_TABLE_NAME', ''))
queue_table = dynamodb.Table(os.environ.get('QUEUE_TABLE_NAME', ''))
templates_table = dynamodb.Table(os.environ.get('TEMPLATES_TABLE_NAME', ''))
cost_tracking_table = dynamodb.Table(os.environ.get('COST_TRACKING_TABLE_NAME', ''))
checkpoint_metadata_table = dynamodb.Table(os.environ.get('CHECKPOINT_METADATA_TABLE_NAME', ''))


class BudgetExceededError(Exception):
    """Raised when job exceeds budget limit."""
    pass


class Worker:
    """ECS Fargate worker for data generation."""

    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        logger.info("Worker initialized")

    def handle_shutdown(self, signum, frame):
        """Handle SIGTERM for Spot interruption (120 seconds to shutdown)."""
        logger.info("Received SIGTERM (Spot interruption), initiating graceful shutdown")
        self.shutdown_requested = True
        # Set alarm to force exit after 100 seconds (leave 20s buffer)
        signal.alarm(100)

    def run(self):
        """Main worker loop - process one job then exit."""
        logger.info("Worker started")
        try:
            job = self.get_next_job()

            if job:
                logger.info(f"Processing job {job['job_id']}")
                self.process_job(job)
            else:
                logger.info("No jobs in queue")

        except Exception as e:
            logger.error(f"Worker error: {str(e)}", exc_info=True)
            sys.exit(1)

        finally:
            logger.info("Worker shutdown complete")
            sys.exit(0)

    def get_next_job(self):
        """Pull next job from QUEUED status and move to RUNNING."""
        try:
            # Query for QUEUED jobs (oldest first)
            response = queue_table.query(
                KeyConditionExpression='#status = :queued',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':queued': 'QUEUED'},
                Limit=1,
                ScanIndexForward=True  # Oldest first (FIFO)
            )

            if not response['Items']:
                logger.info("No jobs in queue, sleeping...")
                time.sleep(30)
                return None

            job_item = response['Items'][0]
            job_id = job_item['job_id']

            # Get full job details from Jobs table
            job_response = jobs_table.get_item(Key={'job_id': job_id})
            if 'Item' not in job_response:
                logger.error(f"Job {job_id} in queue but not in Jobs table")
                # Remove from queue
                queue_table.delete_item(
                    Key={
                        'status': 'QUEUED',
                        'job_id_timestamp': job_item['job_id_timestamp']
                    }
                )
                return None

            job = job_response['Item']

            # Atomically move from QUEUED to RUNNING
            try:
                # Delete from QUEUED queue
                queue_table.delete_item(
                    Key={
                        'status': 'QUEUED',
                        'job_id_timestamp': job_item['job_id_timestamp']
                    },
                    ConditionExpression='attribute_exists(#status)',
                    ExpressionAttributeNames={'#status': 'status'}
                )

                # Add to RUNNING queue
                queue_table.put_item(Item={
                    'status': 'RUNNING',
                    'job_id_timestamp': job_item['job_id_timestamp'],
                    'job_id': job_id,
                    'task_arn': os.environ.get('ECS_TASK_ARN', 'local'),
                    'started_at': datetime.utcnow().isoformat()
                })

                # Update job status in Jobs table
                jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression='SET #status = :running, started_at = :now, task_arn = :task, updated_at = :now',
                    ConditionExpression='#status = :queued',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':running': 'RUNNING',
                        ':queued': 'QUEUED',
                        ':now': datetime.utcnow().isoformat(),
                        ':task': os.environ.get('ECS_TASK_ARN', 'local')
                    }
                )

                logger.info(f"Claimed job {job_id} and moved to RUNNING")
                return job

            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    logger.warning(f"Job {job_id} already claimed by another worker")
                    return None
                raise

        except Exception as e:
            logger.error(f"Error getting next job: {str(e)}", exc_info=True)
            return None

    def process_job(self, job):
        """Process a single job end-to-end."""
        job_id = job['job_id']

        try:
            # Generate data (implemented in Task 4)
            self.generate_data(job)

            # Mark job as complete
            self.mark_job_complete(job_id)

        except BudgetExceededError:
            self.mark_job_budget_exceeded(job_id)

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)
            self.mark_job_failed(job_id, str(e))

    def generate_data(self, job):
        """Main data generation loop - implementation in Task 4."""
        logger.info(f"generate_data called for job {job['job_id']} (stub)")
        # This will be fully implemented in Tasks 4-7
        pass

    def mark_job_complete(self, job_id):
        """Mark job as COMPLETED."""
        now = datetime.utcnow().isoformat()

        # Update Jobs table
        jobs_table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #status = :status, completed_at = :now, updated_at = :now',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':now': now
            }
        )

        # Find and move queue item from RUNNING to COMPLETED
        try:
            # Query for this job in RUNNING queue
            response = queue_table.query(
                KeyConditionExpression='#status = :running',
                FilterExpression='job_id = :job_id',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':running': 'RUNNING',
                    ':job_id': job_id
                }
            )

            if response['Items']:
                item = response['Items'][0]

                # Delete from RUNNING
                queue_table.delete_item(
                    Key={
                        'status': 'RUNNING',
                        'job_id_timestamp': item['job_id_timestamp']
                    }
                )

                # Add to COMPLETED
                queue_table.put_item(Item={
                    'status': 'COMPLETED',
                    'job_id_timestamp': item['job_id_timestamp'],
                    'job_id': job_id,
                    'completed_at': now
                })

        except Exception as e:
            logger.warning(f"Error updating queue for completed job {job_id}: {str(e)}")

        logger.info(f"Job {job_id} marked as COMPLETED")

    def mark_job_failed(self, job_id, error_message):
        """Mark job as FAILED."""
        now = datetime.utcnow().isoformat()

        # Update Jobs table
        jobs_table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #status = :status, error_message = :error, updated_at = :now',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'FAILED',
                ':error': error_message[:1000],  # Limit error message length
                ':now': now
            }
        )

        # Move queue item from RUNNING to FAILED
        try:
            response = queue_table.query(
                KeyConditionExpression='#status = :running',
                FilterExpression='job_id = :job_id',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':running': 'RUNNING',
                    ':job_id': job_id
                }
            )

            if response['Items']:
                item = response['Items'][0]

                queue_table.delete_item(
                    Key={
                        'status': 'RUNNING',
                        'job_id_timestamp': item['job_id_timestamp']
                    }
                )

                queue_table.put_item(Item={
                    'status': 'FAILED',
                    'job_id_timestamp': item['job_id_timestamp'],
                    'job_id': job_id,
                    'failed_at': now,
                    'error_message': error_message[:1000]
                })

        except Exception as e:
            logger.warning(f"Error updating queue for failed job {job_id}: {str(e)}")

        logger.error(f"Job {job_id} marked as FAILED: {error_message}")

    def mark_job_budget_exceeded(self, job_id):
        """Mark job as BUDGET_EXCEEDED."""
        now = datetime.utcnow().isoformat()

        # Update Jobs table
        jobs_table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #status = :status, updated_at = :now',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'BUDGET_EXCEEDED',
                ':now': now
            }
        )

        # Move queue item
        try:
            response = queue_table.query(
                KeyConditionExpression='#status = :running',
                FilterExpression='job_id = :job_id',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':running': 'RUNNING',
                    ':job_id': job_id
                }
            )

            if response['Items']:
                item = response['Items'][0]

                queue_table.delete_item(
                    Key={
                        'status': 'RUNNING',
                        'job_id_timestamp': item['job_id_timestamp']
                    }
                )

                queue_table.put_item(Item={
                    'status': 'BUDGET_EXCEEDED',
                    'job_id_timestamp': item['job_id_timestamp'],
                    'job_id': job_id,
                    'stopped_at': now
                })

        except Exception as e:
            logger.warning(f"Error updating queue for budget exceeded job {job_id}: {str(e)}")

        logger.warning(f"Job {job_id} exceeded budget limit")


if __name__ == "__main__":
    worker = Worker()
    worker.run()
