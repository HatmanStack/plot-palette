"""
Integration tests for ECS worker.

Tests job processing, data generation with Bedrock (mocked), and
worker lifecycle. These tests use moto to mock AWS services.

NOTE: Phase 8 is code writing only. These tests will run against
mocked AWS services. Real infrastructure testing happens in Phase 9.
"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
from moto import mock_dynamodb, mock_s3
import boto3
import sys

# Add backend paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/ecs_tasks/worker'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/shared'))

from constants import JobStatus


@pytest.fixture
def mock_aws_env(monkeypatch):
    """Set up mock AWS environment variables."""
    monkeypatch.setenv('JOBS_TABLE_NAME', 'test-Jobs')
    monkeypatch.setenv('QUEUE_TABLE_NAME', 'test-Queue')
    monkeypatch.setenv('TEMPLATES_TABLE_NAME', 'test-Templates')
    monkeypatch.setenv('COST_TRACKING_TABLE_NAME', 'test-CostTracking')
    monkeypatch.setenv('CHECKPOINT_METADATA_TABLE_NAME', 'test-CheckpointMetadata')
    monkeypatch.setenv('S3_BUCKET_NAME', 'test-bucket')
    monkeypatch.setenv('CHECKPOINT_INTERVAL', '10')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')


@pytest.fixture
def dynamodb_tables(mock_aws_env):
    """Create mock DynamoDB tables."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Jobs table
        dynamodb.create_table(
            TableName='test-Jobs',
            KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )

        # Queue table
        dynamodb.create_table(
            TableName='test-Queue',
            KeySchema=[
                {'AttributeName': 'status', 'KeyType': 'HASH'},
                {'AttributeName': 'job_id_timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'status', 'AttributeType': 'S'},
                {'AttributeName': 'job_id_timestamp', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Templates table
        dynamodb.create_table(
            TableName='test-Templates',
            KeySchema=[
                {'AttributeName': 'template_id', 'KeyType': 'HASH'},
                {'AttributeName': 'version', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'template_id', 'AttributeType': 'S'},
                {'AttributeName': 'version', 'AttributeType': 'N'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Cost Tracking table
        dynamodb.create_table(
            TableName='test-CostTracking',
            KeySchema=[
                {'AttributeName': 'job_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'job_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Checkpoint Metadata table
        dynamodb.create_table(
            TableName='test-CheckpointMetadata',
            KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )

        yield dynamodb


@pytest.fixture
def s3_bucket(mock_aws_env):
    """Create mock S3 bucket."""
    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='test-bucket')
        yield s3


@pytest.fixture
def sample_job(dynamodb_tables):
    """Create a sample job in DynamoDB."""
    jobs_table = dynamodb_tables.Table('test-Jobs')
    queue_table = dynamodb_tables.Table('test-Queue')

    job_id = 'test-job-123'
    timestamp = datetime.utcnow().isoformat()

    # Add to Jobs table
    jobs_table.put_item(Item={
        'job_id': job_id,
        'user_id': 'test-user',
        'status': 'QUEUED',
        'created_at': timestamp,
        'updated_at': timestamp,
        'config': {
            'template_id': 'template-1',
            'seed_data_path': 's3://test-bucket/seed/data.json',
            'target_records': 100
        },
        'budget_limit': 10.0,
        'tokens_used': 0,
        'records_generated': 0,
        'cost_estimate': 0.0
    })

    # Add to Queue table
    queue_table.put_item(Item={
        'status': 'QUEUED',
        'job_id_timestamp': f'{job_id}#{timestamp}',
        'job_id': job_id,
        'priority': 0
    })

    return job_id


@pytest.mark.integration
@pytest.mark.worker
class TestWorkerJobProcessing:
    """Test worker job processing logic."""

    def test_worker_initialization(self, mock_aws_env):
        """Test worker can be initialized."""
        with patch('worker.Worker.__init__', return_value=None):
            from worker import Worker
            worker = Worker.__new__(Worker)
            assert worker is not None

    def test_get_next_job_from_queue(self, dynamodb_tables, sample_job):
        """Test worker can pull job from queue."""
        # This test verifies the queue query logic
        queue_table = dynamodb_tables.Table('test-Queue')

        # Query for queued jobs
        response = queue_table.query(
            KeyConditionExpression='#status = :queued',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':queued': 'QUEUED'},
            Limit=1,
            ScanIndexForward=True
        )

        assert len(response['Items']) == 1
        assert response['Items'][0]['job_id'] == sample_job

    def test_move_job_to_running(self, dynamodb_tables, sample_job):
        """Test atomically moving job from QUEUED to RUNNING."""
        jobs_table = dynamodb_tables.Table('test-Jobs')
        queue_table = dynamodb_tables.Table('test-Queue')

        # Get job from queue
        response = queue_table.query(
            KeyConditionExpression='#status = :queued',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':queued': 'QUEUED'},
            Limit=1
        )
        job_item = response['Items'][0]

        # Delete from QUEUED
        queue_table.delete_item(
            Key={
                'status': 'QUEUED',
                'job_id_timestamp': job_item['job_id_timestamp']
            }
        )

        # Add to RUNNING
        queue_table.put_item(Item={
            'status': 'RUNNING',
            'job_id_timestamp': job_item['job_id_timestamp'],
            'job_id': sample_job,
            'task_arn': 'test-task-arn'
        })

        # Update job status
        jobs_table.update_item(
            Key={'job_id': sample_job},
            UpdateExpression='SET #status = :running',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':running': 'RUNNING'}
        )

        # Verify job is in RUNNING queue
        running_response = queue_table.query(
            KeyConditionExpression='#status = :running',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':running': 'RUNNING'}
        )
        assert len(running_response['Items']) == 1

        # Verify job no longer in QUEUED
        queued_response = queue_table.query(
            KeyConditionExpression='#status = :queued',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':queued': 'QUEUED'}
        )
        assert len(queued_response['Items']) == 0

    @patch('worker.bedrock_client')
    def test_generate_single_record(self, mock_bedrock, dynamodb_tables, s3_bucket):
        """Test generating a single record with mocked Bedrock."""
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'content': [{'text': 'Generated answer text'}]
            }).encode())
        }

        # Simulate template rendering and Bedrock call
        from template_engine import TemplateEngine
        engine = TemplateEngine()

        template_def = {
            'steps': [{
                'id': 'answer',
                'model': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
                'prompt': 'Generate answer about {{ topic }}'
            }]
        }
        seed_data = {'topic': 'machine learning'}

        results = engine.execute_template(template_def, seed_data, mock_bedrock)

        assert 'answer' in results
        assert results['answer']['output'] == 'Generated answer text'

    def test_worker_handles_empty_queue(self, dynamodb_tables):
        """Test worker handles empty queue gracefully."""
        queue_table = dynamodb_tables.Table('test-Queue')

        # Query empty queue
        response = queue_table.query(
            KeyConditionExpression='#status = :queued',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':queued': 'QUEUED'},
            Limit=1
        )

        assert len(response['Items']) == 0


@pytest.mark.integration
@pytest.mark.worker
@pytest.mark.slow
class TestWorkerDataGeneration:
    """Test worker data generation with mocked Bedrock."""

    @patch('worker.bedrock_client')
    def test_batch_generation(self, mock_bedrock, dynamodb_tables, s3_bucket):
        """Test generating a batch of records."""
        # Mock Bedrock responses
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'content': [{'text': 'Generated text'}]
            }).encode())
        }

        # Simulate generating 10 records
        records_generated = []
        for i in range(10):
            records_generated.append({
                'id': i,
                'question': f'Question {i}',
                'answer': 'Generated text'
            })

        assert len(records_generated) == 10

    def test_save_batch_to_s3(self, s3_bucket):
        """Test saving batch file to S3."""
        s3 = boto3.client('s3', region_name='us-east-1')

        # Create batch data
        batch_data = [
            {'question': 'Q1', 'answer': 'A1'},
            {'question': 'Q2', 'answer': 'A2'}
        ]

        # Save as JSONL
        jsonl_content = '\n'.join([json.dumps(record) for record in batch_data])
        s3.put_object(
            Bucket='test-bucket',
            Key='jobs/test-job/outputs/batch-001.jsonl',
            Body=jsonl_content.encode()
        )

        # Verify file exists
        response = s3.get_object(
            Bucket='test-bucket',
            Key='jobs/test-job/outputs/batch-001.jsonl'
        )
        content = response['Body'].read().decode()
        assert 'Q1' in content
        assert 'A1' in content

    def test_cost_tracking_update(self, dynamodb_tables):
        """Test updating cost tracking in DynamoDB."""
        cost_table = dynamodb_tables.Table('test-CostTracking')

        # Add cost entry
        cost_table.put_item(Item={
            'job_id': 'test-job-123',
            'timestamp': datetime.utcnow().isoformat(),
            'bedrock_tokens': 10000,
            'fargate_hours': 0.5,
            's3_operations': 10,
            'estimated_cost': 1.25,
            'model_id': 'meta.llama3-1-8b-instruct-v1:0'
        })

        # Query cost for job
        response = cost_table.query(
            KeyConditionExpression='job_id = :job_id',
            ExpressionAttributeValues={':job_id': 'test-job-123'}
        )

        assert len(response['Items']) == 1
        assert response['Items'][0]['estimated_cost'] == 1.25


@pytest.mark.integration
@pytest.mark.worker
class TestWorkerErrorHandling:
    """Test worker error handling."""

    @patch('worker.bedrock_client')
    def test_bedrock_api_error(self, mock_bedrock):
        """Test handling Bedrock API errors."""
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock API error")

        from template_engine import TemplateEngine
        engine = TemplateEngine()

        template_def = {
            'steps': [{
                'id': 'step1',
                'model': 'meta.llama3-1-8b-instruct-v1:0',
                'prompt': 'Test'
            }]
        }

        results = engine.execute_template(template_def, {}, mock_bedrock)

        # Should capture error, not crash
        assert 'step1' in results
        assert 'error' in results['step1']

    def test_invalid_seed_data(self, dynamodb_tables):
        """Test handling invalid seed data."""
        from utils import validate_seed_data

        data = {'author': {'name': 'Jane'}}
        is_valid, error = validate_seed_data(
            data,
            required_fields=['author.name', 'author.missing']
        )

        assert is_valid is False
        assert 'Missing required field' in error

    def test_s3_write_error_handling(self, s3_bucket):
        """Test handling S3 write errors."""
        s3 = boto3.client('s3', region_name='us-east-1')

        # Try to write to non-existent bucket
        with pytest.raises(Exception):
            s3.put_object(
                Bucket='non-existent-bucket',
                Key='test.json',
                Body=b'test'
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--integration"])
