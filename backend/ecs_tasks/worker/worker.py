"""
Plot Palette - ECS Generation Worker

This worker pulls jobs from the DynamoDB queue, generates synthetic data using
AWS Bedrock, and implements checkpoint-based graceful shutdown for Spot interruptions.
"""

import io
import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import ClientError
from template_engine import TemplateEngine

# Import from shared constants
sys.path.append('/app')
from shared.constants import FARGATE_SPOT_PRICING, MODEL_PRICING, S3_PRICING
from shared.models import CostBreakdown, CostComponents

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

# Validate required environment variables
required_env_vars = {
    'JOBS_TABLE_NAME': 'Jobs table name',
    'QUEUE_TABLE_NAME': 'Queue table name',
    'TEMPLATES_TABLE_NAME': 'Templates table name',
    'COST_TRACKING_TABLE_NAME': 'Cost tracking table name',
    'CHECKPOINT_METADATA_TABLE_NAME': 'Checkpoint metadata table name',
}

for var_name, description in required_env_vars.items():
    if not os.environ.get(var_name):
        raise ValueError(f"Missing required environment variable: {var_name} ({description})")

# DynamoDB tables
jobs_table = dynamodb.Table(os.environ['JOBS_TABLE_NAME'])
queue_table = dynamodb.Table(os.environ['QUEUE_TABLE_NAME'])
templates_table = dynamodb.Table(os.environ['TEMPLATES_TABLE_NAME'])
cost_tracking_table = dynamodb.Table(os.environ['COST_TRACKING_TABLE_NAME'])
checkpoint_metadata_table = dynamodb.Table(os.environ['CHECKPOINT_METADATA_TABLE_NAME'])


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
        signal.signal(signal.SIGALRM, self.handle_alarm_timeout)
        self.template_engine = TemplateEngine()
        logger.info("Worker initialized")

    def handle_shutdown(self, signum, frame):
        """Handle SIGTERM for Spot interruption (120 seconds to shutdown)."""
        logger.info("Received SIGTERM (Spot interruption), initiating graceful shutdown")
        self.shutdown_requested = True
        # Set alarm to force exit after 100 seconds (leave 20s buffer)
        signal.alarm(100)

    def handle_alarm_timeout(self, signum, frame):
        """Handle SIGALRM — graceful shutdown timed out, force exit."""
        logger.error("SIGALRM: graceful shutdown timed out, forcing exit")
        sys.exit(1)

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
                logger.info("No jobs in queue")
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

        # Budget limit may be stored as string in DynamoDB, normalize to float
        budget_limit_raw = config.get('budget_limit', job.get('budget_limit', 100.0))
        try:
            budget_limit = float(budget_limit_raw)
        except (TypeError, ValueError):
            logger.warning(f"Invalid budget_limit value: {budget_limit_raw}, using default 100.0")
            budget_limit = 100.0

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
        running_cost = checkpoint.get('cost_accumulated', 0.0)

        for i in range(start_index, target_records):
            if self.shutdown_requested:
                logger.info("Shutdown requested, checkpointing and exiting")
                self.save_checkpoint(job_id, checkpoint)
                self.save_batch(job_id, batch_number, batch_records)
                break

            # Check budget using in-memory running cost (updated after every call)
            if running_cost >= budget_limit:
                logger.warning(f"Budget limit reached: ${running_cost:.2f} >= ${budget_limit:.2f}")
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

                # Determine model_id for cost tracking
                step_model_id = 'anthropic.claude-3-5-sonnet-20241022-v2:0'
                if isinstance(result, dict):
                    for step_result in result.values():
                        if isinstance(step_result, dict) and 'model' in step_result:
                            step_model_id = step_result['model']
                            break

                # Update checkpoint counters
                checkpoint['records_generated'] = i + 1
                checkpoint['tokens_used'] = checkpoint.get('tokens_used', 0) + self.estimate_tokens(result, step_model_id)
                checkpoint['model_id'] = step_model_id

                # Update in-memory running cost after every Bedrock call
                running_cost += self.estimate_single_call_cost(result, step_model_id)

                # Checkpoint every N records
                if (i + 1) % self.CHECKPOINT_INTERVAL == 0:
                    self.save_batch(job_id, batch_number, batch_records)
                    # Calculate and store cost in checkpoint
                    total_cost = self.update_cost_tracking(job_id, checkpoint)
                    checkpoint['cost_accumulated'] = total_cost
                    self.save_checkpoint(job_id, checkpoint)
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

        # Final checkpoint with cost update
        checkpoint['completed'] = True
        total_cost = self.update_cost_tracking(job_id, checkpoint)
        checkpoint['cost_accumulated'] = total_cost
        self.save_checkpoint(job_id, checkpoint)
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

    def estimate_tokens(self, result, model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"):
        """
        Estimate tokens used in generation using model-specific approximation.

        Args:
            result: Generation result (will be JSON-serialized)
            model_id: Model identifier for model-specific estimation

        Returns:
            int: Estimated token count
        """
        text = json.dumps(result)
        # Use model-specific token estimation
        # Claude: ~3.5 chars/token, Llama/Mistral: ~4 chars/token
        if 'claude' in model_id.lower():
            return max(1, int(len(text) / 3.5))
        else:
            return max(1, int(len(text) / 4))

    def load_checkpoint(self, job_id):
        """Load checkpoint from S3 with version from DynamoDB."""
        bucket = os.environ.get('BUCKET_NAME', '')
        key = f"jobs/{job_id}/checkpoint.json"

        try:
            # Load checkpoint blob from S3
            response = s3_client.get_object(Bucket=bucket, Key=key)
            checkpoint_data = json.loads(response['Body'].read())

            # Capture S3 ETag for conditional writes
            checkpoint_data['_etag'] = response.get('ETag', '')

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

    def save_checkpoint(self, job_id, checkpoint_data, retry_count=0):
        """Save checkpoint using DynamoDB for concurrency control and S3 for blob storage."""
        MAX_RETRIES = 3

        if retry_count >= MAX_RETRIES:
            logger.error(f"Max checkpoint retries ({MAX_RETRIES}) exceeded for job {job_id}")
            raise Exception(f"Failed to save checkpoint after {MAX_RETRIES} retries due to persistent conflicts")

        bucket = os.environ.get('BUCKET_NAME', '')
        s3_key = f"jobs/{job_id}/checkpoint.json"

        checkpoint_data['last_updated'] = datetime.utcnow().isoformat()

        # Get current version from checkpoint_data (or 0 for first write)
        current_version = checkpoint_data.get('_version', 0)
        new_version = current_version + 1

        # Build serializable dict excluding internal metadata keys
        serializable_data = {k: v for k, v in checkpoint_data.items() if k not in ('_version', '_etag')}
        checkpoint_json = json.dumps(serializable_data, indent=2)

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

            # Successfully claimed write permission - now write to S3 with ETag condition
            put_kwargs = {
                'Bucket': bucket,
                'Key': s3_key,
                'Body': checkpoint_json.encode('utf-8'),
                'ContentType': 'application/json',
            }
            stored_etag = checkpoint_data.get('_etag')
            if stored_etag:
                put_kwargs['IfMatch'] = stored_etag

            s3_response = s3_client.put_object(**put_kwargs)

            # Store the new version and ETag for next write
            checkpoint_data['_version'] = new_version
            checkpoint_data['_etag'] = s3_response.get('ETag', '')

            logger.info(f"Saved checkpoint for job {job_id}: {checkpoint_data['records_generated']} records (version {new_version})")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ('ConditionalCheckFailedException', 'PreconditionFailed', '412'):
                logger.warning(f"Checkpoint conflict ({error_code}) for job {job_id} (retry {retry_count + 1}/{MAX_RETRIES}), reloading and merging")

                # Another task updated checkpoint - reload and merge
                current_checkpoint = self.load_checkpoint(job_id)

                # Merge strategy: take maximum records_generated
                if checkpoint_data['records_generated'] > current_checkpoint['records_generated']:
                    # Brief exponential backoff before retry
                    backoff_ms = (2 ** retry_count) * 100  # 100ms, 200ms, 400ms
                    time.sleep(backoff_ms / 1000.0)

                    # Retry save with new version
                    checkpoint_data['_version'] = current_checkpoint['_version']
                    self.save_checkpoint(job_id, checkpoint_data, retry_count + 1)
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
                # Access nested DynamoDB structure: estimated_cost.M.total.N
                cost_map = response['Items'][0].get('estimated_cost', {})
                if isinstance(cost_map, dict) and 'M' in cost_map:
                    # New typed format
                    total_value = cost_map['M'].get('total', {}).get('N', '0.0')
                else:
                    # Fallback for old flat format
                    total_value = cost_map.get('N', '0.0')
                return float(total_value)
            else:
                return 0.0

        except Exception as e:
            logger.error(f"Error calculating cost: {str(e)}", exc_info=True)
            # Fail open to avoid blocking generation
            return 0.0

    def estimate_single_call_cost(self, result, model_id):
        """Estimate cost of a single Bedrock call including input and output tokens."""
        pricing = MODEL_PRICING.get(model_id, MODEL_PRICING['anthropic.claude-3-5-sonnet-20241022-v2:0'])
        tokens = self.estimate_tokens(result, model_id)
        # Assume 40/60 input/output token split
        input_tokens = int(tokens * 0.4)
        output_tokens = tokens - input_tokens
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        return input_cost + output_cost

    def update_cost_tracking(self, job_id, checkpoint):
        """Write cost tracking record to DynamoDB with 90-day TTL."""
        tokens_used = checkpoint.get('tokens_used', 0)
        model_id = checkpoint.get('model_id', 'anthropic.claude-3-5-sonnet-20241022-v2:0')

        # Calculate Bedrock cost using both input and output pricing
        pricing = MODEL_PRICING.get(model_id, MODEL_PRICING['anthropic.claude-3-5-sonnet-20241022-v2:0'])
        # Assume 40/60 input/output token split
        input_tokens = int(tokens_used * 0.4)
        output_tokens = tokens_used - input_tokens
        bedrock_cost = (input_tokens / 1_000_000) * pricing['input'] + \
                       (output_tokens / 1_000_000) * pricing['output']

        # Calculate Fargate cost (elapsed time)
        started_at_str = checkpoint.get('started_at')
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid started_at format: {started_at_str}, using current time")
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

        # Create typed cost breakdown
        cost_breakdown = CostBreakdown(
            job_id=job_id,
            timestamp=datetime.utcnow(),
            bedrock_tokens=tokens_used,
            fargate_hours=round(fargate_hours, 4),
            s3_operations=s3_puts,
            estimated_cost=CostComponents(
                bedrock=round(bedrock_cost, 4),
                fargate=round(fargate_cost, 4),
                s3=round(s3_cost, 6),
                total=round(total_cost, 4)
            )
        )

        try:
            cost_tracking_table.put_item(Item=cost_breakdown.to_table_item())
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
        """Export batch files to final formats (JSONL, Parquet, CSV)."""
        logger.info(f"Exporting data for job {job_id}")

        output_format = config.get('output_format', 'JSONL')
        partition_strategy = config.get('partition_strategy', 'none')

        bucket = os.environ.get('BUCKET_NAME', '')

        # Normalize output_format to set for consistent checking
        if isinstance(output_format, str):
            formats = {output_format}
        elif isinstance(output_format, list):
            formats = set(output_format)
        else:
            formats = {'JSONL'}

        # Each format gets its own generator (generators can't be reused)
        # S3 reads are cheap; memory is not
        record_count = 0

        if 'JSONL' in formats:
            record_count = self.export_jsonl(job_id, self.load_all_batches(job_id), partition_strategy, bucket)

        if 'PARQUET' in formats:
            record_count = self.export_parquet(job_id, self.load_all_batches(job_id), partition_strategy, bucket)

        if 'CSV' in formats:
            record_count = self.export_csv(job_id, self.load_all_batches(job_id), partition_strategy, bucket)

        logger.info(f"Export complete for job {job_id}: {record_count} records in {len(formats)} format(s)")

    def load_all_batches(self, job_id):
        """Load all batch files from S3 as a generator to avoid OOM."""
        bucket = os.environ.get('BUCKET_NAME', '')
        prefix = f"jobs/{job_id}/outputs/"

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    if not key.endswith('.jsonl'):
                        continue

                    # Stream batch file line by line
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    for line in response['Body'].iter_lines():
                        decoded = line.decode('utf-8').strip() if isinstance(line, bytes) else line.strip()
                        if decoded:
                            yield json.loads(decoded)

        except Exception as e:
            logger.error(f"Error loading batches: {str(e)}", exc_info=True)

    def export_jsonl(self, job_id, records, partition_strategy, bucket):
        """Export as JSONL format using S3 multipart upload for streaming."""
        key = f"jobs/{job_id}/exports/dataset.jsonl"
        PART_SIZE = 5 * 1024 * 1024  # 5MB minimum for multipart

        # Start multipart upload
        mpu = s3_client.create_multipart_upload(
            Bucket=bucket, Key=key, ContentType='application/x-ndjson'
        )
        upload_id = mpu['UploadId']
        parts = []
        buffer = io.BytesIO()
        part_number = 1
        record_count = 0

        try:
            for record in records:
                line = json.dumps(record) + '\n'
                buffer.write(line.encode('utf-8'))
                record_count += 1

                if buffer.tell() >= PART_SIZE:
                    buffer.seek(0)
                    response = s3_client.upload_part(
                        Bucket=bucket, Key=key, UploadId=upload_id,
                        PartNumber=part_number, Body=buffer.read()
                    )
                    parts.append({'PartNumber': part_number, 'ETag': response['ETag']})
                    part_number += 1
                    buffer = io.BytesIO()

            # Upload remaining data
            if buffer.tell() > 0:
                buffer.seek(0)
                if not parts:
                    # Less than one part — abort multipart and use simple put
                    s3_client.abort_multipart_upload(
                        Bucket=bucket, Key=key, UploadId=upload_id
                    )
                    s3_client.put_object(
                        Bucket=bucket, Key=key,
                        Body=buffer.read(), ContentType='application/x-ndjson'
                    )
                    logger.info(f"Exported JSONL: {key} ({record_count} records)")
                    return record_count
                else:
                    response = s3_client.upload_part(
                        Bucket=bucket, Key=key, UploadId=upload_id,
                        PartNumber=part_number, Body=buffer.read()
                    )
                    parts.append({'PartNumber': part_number, 'ETag': response['ETag']})

            if parts:
                s3_client.complete_multipart_upload(
                    Bucket=bucket, Key=key, UploadId=upload_id,
                    MultipartUpload={'Parts': parts}
                )
            else:
                # No records at all
                s3_client.abort_multipart_upload(
                    Bucket=bucket, Key=key, UploadId=upload_id
                )
                s3_client.put_object(
                    Bucket=bucket, Key=key, Body=b'', ContentType='application/x-ndjson'
                )

            logger.info(f"Exported JSONL: {key} ({record_count} records)")

        except Exception:
            s3_client.abort_multipart_upload(
                Bucket=bucket, Key=key, UploadId=upload_id
            )
            raise

        return record_count

    def export_parquet(self, job_id, records, partition_strategy, bucket):
        """Export as Parquet format using chunked writes."""
        CHUNK_SIZE = 10_000

        if partition_strategy != 'none':
            logger.warning(f"Parquet export does not support partition_strategy='{partition_strategy}', falling back to single file")

        key = f"jobs/{job_id}/exports/dataset.parquet"
        buffer = io.BytesIO()
        writer = None
        record_count = 0

        chunk = []
        for record in records:
            flat = {
                'id': record['id'],
                'job_id': record['job_id'],
                'timestamp': record['timestamp'],
                'seed_data_id': record.get('seed_data_id', 'unknown'),
                'generation_result': json.dumps(record['generation_result'])
            }
            chunk.append(flat)
            record_count += 1

            if len(chunk) >= CHUNK_SIZE:
                table = pa.Table.from_pandas(pd.DataFrame(chunk))
                if writer is None:
                    writer = pq.ParquetWriter(buffer, table.schema)
                writer.write_table(table)
                chunk = []

        # Write remaining records
        if chunk:
            table = pa.Table.from_pandas(pd.DataFrame(chunk))
            if writer is None:
                writer = pq.ParquetWriter(buffer, table.schema)
            writer.write_table(table)

        if writer:
            writer.close()

        # Upload to S3
        buffer.seek(0)
        s3_client.put_object(
            Bucket=bucket, Key=key,
            Body=buffer.read(), ContentType='application/octet-stream'
        )

        logger.info(f"Exported Parquet: {key} ({record_count} records)")
        return record_count

    def export_csv(self, job_id, records, partition_strategy, bucket):
        """Export as CSV format using chunked writes."""
        CHUNK_SIZE = 10_000

        if partition_strategy != 'none':
            logger.warning(f"CSV export does not support partition_strategy='{partition_strategy}', falling back to single file")

        key = f"jobs/{job_id}/exports/dataset.csv"
        buffer = io.StringIO()
        record_count = 0
        header_written = False

        chunk = []
        for record in records:
            flat = {
                'id': record['id'],
                'job_id': record['job_id'],
                'timestamp': record['timestamp'],
                'seed_data_id': record.get('seed_data_id', 'unknown'),
                'generation_result': json.dumps(record['generation_result'])
            }
            chunk.append(flat)
            record_count += 1

            if len(chunk) >= CHUNK_SIZE:
                df = pd.DataFrame(chunk)
                buffer.write(df.to_csv(index=False, header=not header_written))
                header_written = True
                chunk = []

        # Write remaining records
        if chunk:
            df = pd.DataFrame(chunk)
            buffer.write(df.to_csv(index=False, header=not header_written))

        s3_client.put_object(
            Bucket=bucket, Key=key,
            Body=buffer.getvalue().encode('utf-8'), ContentType='text/csv'
        )

        logger.info(f"Exported CSV: {key} ({record_count} records)")
        return record_count

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
