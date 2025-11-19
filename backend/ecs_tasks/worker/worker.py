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
import random
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from template_engine import TemplateEngine

# Import from shared constants
import sys
sys.path.append('/app')
from shared.constants import MODEL_PRICING, FARGATE_SPOT_PRICING, S3_PRICING

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

    # Checkpoint every N records
    CHECKPOINT_INTERVAL = int(os.environ.get('CHECKPOINT_INTERVAL', '50'))

    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        self.template_engine = TemplateEngine()
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
        """Main data generation loop."""
        job_id = job['job_id']
        config = job['config']
        budget_limit = job.get('budget_limit', 100.0)

        # Load template from DynamoDB
        template = self.load_template(config['template_id'])

        # Load seed data from S3
        seed_data_list = self.load_seed_data(config['seed_data_path'])

        # Load or create checkpoint
        checkpoint = self.load_checkpoint(job_id)
        start_index = checkpoint.get('records_generated', 0)

        # Store job start time in checkpoint if not already there
        if 'started_at' not in checkpoint:
            checkpoint['started_at'] = datetime.utcnow().isoformat()

        target_records = config['num_records']

        logger.info(f"Generating {target_records} records for job {job_id}, starting at {start_index}")

        batch_records = []
        batch_number = checkpoint.get('current_batch', 1)

        for i in range(start_index, target_records):
            if self.shutdown_requested:
                logger.info("Shutdown requested, checkpointing and exiting")
                self.save_checkpoint(job_id, checkpoint)
                self.save_batch(job_id, batch_number, batch_records)
                break

            # Check budget before each generation (stub for now, implemented in Task 6)
            current_cost = self.calculate_current_cost(job_id)
            if current_cost >= budget_limit:
                logger.warning(f"Budget limit reached: ${current_cost:.2f} >= ${budget_limit:.2f}")
                raise BudgetExceededError(f"Exceeded budget limit of ${budget_limit}")

            # Select random seed data
            seed_data = random.choice(seed_data_list)

            # Generate record using template
            try:
                result = self.template_engine.execute_template(
                    template['template_definition'],
                    seed_data,
                    bedrock_client
                )

                record = {
                    'id': f"{job_id}-{i}",
                    'job_id': job_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'seed_data_id': seed_data.get('_id', 'unknown'),
                    'generation_result': result
                }

                batch_records.append(record)

                # Update checkpoint counters
                checkpoint['records_generated'] = i + 1
                checkpoint['tokens_used'] = checkpoint.get('tokens_used', 0) + self.estimate_tokens(result)

                # Checkpoint every N records
                if (i + 1) % self.CHECKPOINT_INTERVAL == 0:
                    self.save_batch(job_id, batch_number, batch_records)
                    self.save_checkpoint(job_id, checkpoint)
                    self.update_cost_tracking(job_id, checkpoint)
                    self.update_job_progress(job_id, checkpoint)

                    batch_records = []
                    batch_number += 1
                    checkpoint['current_batch'] = batch_number

            except Exception as e:
                logger.error(f"Error generating record {i}: {str(e)}")
                # Continue with next record (don't fail entire job for one bad record)
                continue

        # Save final batch
        if batch_records:
            self.save_batch(job_id, batch_number, batch_records)

        # Final checkpoint
        checkpoint['completed'] = True
        self.save_checkpoint(job_id, checkpoint)
        self.update_cost_tracking(job_id, checkpoint)
        self.update_job_progress(job_id, checkpoint)

        # Export data
        self.export_data(job_id, config)

        logger.info(f"Job {job_id} completed: {checkpoint['records_generated']} records generated")

    def load_template(self, template_id):
        """Load template from DynamoDB."""
        try:
            response = templates_table.get_item(
                Key={'template_id': template_id, 'version': 1}
            )
            if 'Item' not in response:
                raise ValueError(f"Template {template_id} not found")

            logger.info(f"Loaded template {template_id}")
            return response['Item']

        except Exception as e:
            logger.error(f"Error loading template {template_id}: {str(e)}", exc_info=True)
            raise

    def load_seed_data(self, s3_path):
        """Load seed data from S3."""
        try:
            bucket = os.environ.get('BUCKET_NAME', '')
            # s3_path format: "seed-data/user-123/data.json"

            response = s3_client.get_object(Bucket=bucket, Key=s3_path)
            data = json.loads(response['Body'].read())

            # Support both single dict and list of dicts
            if isinstance(data, list):
                seed_list = data
            else:
                seed_list = [data]

            logger.info(f"Loaded {len(seed_list)} seed data items from {s3_path}")
            return seed_list

        except Exception as e:
            logger.error(f"Error loading seed data from {s3_path}: {str(e)}", exc_info=True)
            raise

    def estimate_tokens(self, result):
        """Estimate tokens used in generation (rough approximation)."""
        text = json.dumps(result)
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4

    def load_checkpoint(self, job_id):
        """Load checkpoint from S3 with version from DynamoDB."""
        bucket = os.environ.get('BUCKET_NAME', '')
        key = f"jobs/{job_id}/checkpoint.json"

        try:
            # Load checkpoint blob from S3
            response = s3_client.get_object(Bucket=bucket, Key=key)
            checkpoint_data = json.loads(response['Body'].read())

            # Load version from DynamoDB
            metadata_response = checkpoint_metadata_table.get_item(
                Key={'job_id': job_id}
            )
            if 'Item' in metadata_response:
                checkpoint_data['_version'] = metadata_response['Item'].get('version', 0)
            else:
                checkpoint_data['_version'] = 0

            logger.info(f"Loaded checkpoint for job {job_id}: {checkpoint_data['records_generated']} records (version {checkpoint_data['_version']})")
            return checkpoint_data

        except s3_client.exceptions.NoSuchKey:
            logger.info(f"No checkpoint found for job {job_id}, starting fresh")
            return {
                'job_id': job_id,
                'records_generated': 0,
                'current_batch': 1,
                'tokens_used': 0,
                'cost_accumulated': 0.0,
                'last_updated': datetime.utcnow().isoformat(),
                '_version': 0
            }
        except Exception as e:
            logger.error(f"Error loading checkpoint: {str(e)}", exc_info=True)
            # Return empty checkpoint on error
            return {
                'job_id': job_id,
                'records_generated': 0,
                'current_batch': 1,
                'tokens_used': 0,
                'cost_accumulated': 0.0,
                'last_updated': datetime.utcnow().isoformat(),
                '_version': 0
            }

    def save_checkpoint(self, job_id, checkpoint_data):
        """Save checkpoint using DynamoDB for concurrency control and S3 for blob storage."""
        bucket = os.environ.get('BUCKET_NAME', '')
        s3_key = f"jobs/{job_id}/checkpoint.json"

        checkpoint_data['last_updated'] = datetime.utcnow().isoformat()

        # Get current version from checkpoint_data (or 0 for first write)
        current_version = checkpoint_data.pop('_version', 0)
        new_version = current_version + 1

        checkpoint_json = json.dumps(checkpoint_data, indent=2)

        # First, try to claim write permission via DynamoDB conditional update
        try:
            checkpoint_metadata_table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='SET #version = :new_version, records_generated = :records, last_updated = :now',
                ConditionExpression='attribute_not_exists(#version) OR #version = :current_version',
                ExpressionAttributeNames={'#version': 'version'},
                ExpressionAttributeValues={
                    ':new_version': new_version,
                    ':current_version': current_version,
                    ':records': checkpoint_data['records_generated'],
                    ':now': datetime.utcnow().isoformat()
                }
            )

            # Successfully claimed write permission - now write to S3
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=checkpoint_json.encode('utf-8'),
                ContentType='application/json'
            )

            # Store the new version for next write
            checkpoint_data['_version'] = new_version

            logger.info(f"Saved checkpoint for job {job_id}: {checkpoint_data['records_generated']} records (version {new_version})")

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Checkpoint version conflict for job {job_id}, reloading and merging")

                # Another task updated checkpoint - reload and merge
                current_checkpoint = self.load_checkpoint(job_id)

                # Merge strategy: take maximum records_generated
                if checkpoint_data['records_generated'] > current_checkpoint['records_generated']:
                    # Retry save with new version
                    checkpoint_data['_version'] = current_checkpoint['_version']
                    self.save_checkpoint(job_id, checkpoint_data)
                else:
                    logger.info("Current checkpoint is already ahead, skipping save")
            else:
                raise

        except Exception as e:
            logger.error(f"Error saving checkpoint: {str(e)}", exc_info=True)
            raise

    def save_batch(self, job_id, batch_number, records):
        """Save batch of generated records to S3 as JSONL."""
        if not records:
            return

        bucket = os.environ.get('BUCKET_NAME', '')
        key = f"jobs/{job_id}/outputs/batch-{batch_number:04d}.jsonl"

        # Write as JSONL (one JSON object per line)
        jsonl_content = '\n'.join([json.dumps(record) for record in records])

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=jsonl_content.encode('utf-8'),
            ContentType='application/x-ndjson'
        )

        logger.info(f"Saved batch {batch_number} for job {job_id}: {len(records)} records")

    def calculate_current_cost(self, job_id):
        """Query cost tracking table and return latest total cost."""
        try:
            response = cost_tracking_table.query(
                KeyConditionExpression='job_id = :jid',
                ExpressionAttributeValues={':jid': job_id},
                ScanIndexForward=False,  # Descending order (most recent first)
                Limit=1
            )

            if response['Items']:
                latest_cost = response['Items'][0]['estimated_cost']['total']
                return latest_cost
            else:
                return 0.0

        except Exception as e:
            logger.error(f"Error calculating cost: {str(e)}", exc_info=True)
            # Fail open to avoid blocking generation
            return 0.0

    def update_cost_tracking(self, job_id, checkpoint):
        """Write cost tracking record to DynamoDB with 90-day TTL."""
        tokens_used = checkpoint.get('tokens_used', 0)
        records_generated = checkpoint.get('records_generated', 0)

        # Calculate Bedrock cost (simplified - assumes Claude Sonnet average)
        # In real implementation, would track per-model usage
        bedrock_cost = (tokens_used / 1_000_000) * MODEL_PRICING['anthropic.claude-3-5-sonnet-20241022-v2:0']['input']

        # Calculate Fargate cost (elapsed time)
        started_at_str = checkpoint.get('started_at')
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str)
            except:
                started_at = datetime.utcnow()
        else:
            started_at = datetime.utcnow()

        elapsed_seconds = (datetime.utcnow() - started_at).total_seconds()
        fargate_hours = elapsed_seconds / 3600
        # Assume 0.5 vCPU, 1 GB memory
        fargate_cost = (fargate_hours * FARGATE_SPOT_PRICING['vcpu'] * 0.5) + \
                       (fargate_hours * FARGATE_SPOT_PRICING['memory'] * 1.0)

        # Calculate S3 cost (batch uploads + checkpoint saves)
        batch_count = checkpoint.get('current_batch', 1)
        s3_puts = batch_count + (checkpoint['records_generated'] // self.CHECKPOINT_INTERVAL)
        s3_cost = (s3_puts / 1000) * S3_PRICING['PUT']

        total_cost = bedrock_cost + fargate_cost + s3_cost

        # Write to DynamoDB with TTL
        ttl_timestamp = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        try:
            cost_tracking_table.put_item(Item={
                'job_id': job_id,
                'timestamp': datetime.utcnow().isoformat(),
                'bedrock_tokens': tokens_used,
                'fargate_hours': round(fargate_hours, 4),
                's3_operations': s3_puts,
                'estimated_cost': {
                    'bedrock': round(bedrock_cost, 4),
                    'fargate': round(fargate_cost, 4),
                    's3': round(s3_cost, 6),
                    'total': round(total_cost, 4)
                },
                'records_generated': records_generated,
                'ttl': ttl_timestamp
            })

            logger.info(f"Updated cost tracking for job {job_id}: ${total_cost:.4f}")

        except Exception as e:
            logger.error(f"Error writing cost tracking: {str(e)}", exc_info=True)

        return total_cost

    def update_job_progress(self, job_id, checkpoint):
        """Update job record with current progress."""
        try:
            jobs_table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='''
                    SET records_generated = :records,
                        tokens_used = :tokens,
                        cost_estimate = :cost,
                        updated_at = :now
                ''',
                ExpressionAttributeValues={
                    ':records': checkpoint['records_generated'],
                    ':tokens': checkpoint.get('tokens_used', 0),
                    ':cost': checkpoint.get('cost_accumulated', 0.0),
                    ':now': datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"Error updating job progress: {str(e)}", exc_info=True)

    def export_data(self, job_id, config):
        """Export data - stub for Task 7."""
        logger.info(f"export_data called for {job_id} (stub)")
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
