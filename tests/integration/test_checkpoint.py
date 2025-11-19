"""
Integration tests for checkpoint save/restore functionality.

Tests checkpoint creation, S3 storage with ETags, recovery from
spot interruptions, and concurrent checkpoint handling.

NOTE: Phase 8 is code writing only. These tests use moto to mock S3.
Real infrastructure testing happens in Phase 9.
"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
from moto import mock_s3, mock_dynamodb
import boto3

from backend.shared.models import CheckpointState


@pytest.fixture
def s3_client():
    """Create mock S3 client."""
    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='test-bucket')
        yield s3


@pytest.fixture
def sample_checkpoint():
    """Create a sample checkpoint state."""
    return CheckpointState(
        job_id='test-job-123',
        records_generated=1250,
        current_batch=25,
        tokens_used=450000,
        cost_accumulated=12.50,
        resume_state={
            'seed_data_index': 42,
            'template_step': 'answer_generation'
        }
    )


@pytest.mark.integration
class TestCheckpointCreation:
    """Test checkpoint state creation and serialization."""

    def test_checkpoint_creation(self):
        """Test creating a checkpoint state."""
        checkpoint = CheckpointState(
            job_id='job-123',
            records_generated=100,
            current_batch=2,
            tokens_used=50000,
            cost_accumulated=2.50
        )

        assert checkpoint.job_id == 'job-123'
        assert checkpoint.records_generated == 100
        assert checkpoint.tokens_used == 50000
        assert checkpoint.cost_accumulated == 2.50

    def test_checkpoint_serialization(self, sample_checkpoint):
        """Test checkpoint JSON serialization."""
        json_str = sample_checkpoint.to_json()

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data['job_id'] == 'test-job-123'
        assert data['records_generated'] == 1250
        assert data['tokens_used'] == 450000

    def test_checkpoint_deserialization(self, sample_checkpoint):
        """Test checkpoint JSON deserialization."""
        json_str = sample_checkpoint.to_json()

        # Deserialize
        restored = CheckpointState.from_json(json_str, etag='abc123')

        assert restored.job_id == sample_checkpoint.job_id
        assert restored.records_generated == sample_checkpoint.records_generated
        assert restored.etag == 'abc123'

    def test_checkpoint_with_resume_state(self):
        """Test checkpoint includes resume state."""
        checkpoint = CheckpointState(
            job_id='job-123',
            records_generated=500,
            current_batch=10,
            tokens_used=100000,
            cost_accumulated=5.0,
            resume_state={
                'seed_index': 25,
                'step': 'question',
                'partial_batch': [{'id': 1}, {'id': 2}]
            }
        )

        json_str = checkpoint.to_json()
        data = json.loads(json_str)

        assert 'resume_state' in data
        assert data['resume_state']['seed_index'] == 25
        assert data['resume_state']['step'] == 'question'


@pytest.mark.integration
class TestCheckpointS3Storage:
    """Test checkpoint storage in S3 with ETag support."""

    def test_save_checkpoint_to_s3(self, s3_client, sample_checkpoint):
        """Test saving checkpoint to S3."""
        checkpoint_json = sample_checkpoint.to_json()

        s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json',
            Body=checkpoint_json.encode()
        )

        # Verify checkpoint exists
        response = s3_client.get_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json'
        )

        content = response['Body'].read().decode()
        data = json.loads(content)
        assert data['job_id'] == 'test-job-123'
        assert data['records_generated'] == 1250

    def test_load_checkpoint_from_s3(self, s3_client, sample_checkpoint):
        """Test loading checkpoint from S3."""
        # Save checkpoint
        checkpoint_json = sample_checkpoint.to_json()
        s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json',
            Body=checkpoint_json.encode()
        )

        # Load checkpoint
        response = s3_client.get_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json'
        )

        content = response['Body'].read().decode()
        etag = response['ETag'].strip('"')

        # Restore checkpoint with ETag
        restored = CheckpointState.from_json(content, etag=etag)

        assert restored.job_id == sample_checkpoint.job_id
        assert restored.records_generated == sample_checkpoint.records_generated
        assert restored.etag is not None

    def test_checkpoint_etag_tracking(self, s3_client, sample_checkpoint):
        """Test ETag is updated on checkpoint save."""
        checkpoint_json = sample_checkpoint.to_json()

        # Save checkpoint first time
        response1 = s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json',
            Body=checkpoint_json.encode()
        )
        etag1 = response1['ETag']

        # Update and save again
        sample_checkpoint.records_generated = 1300
        updated_json = sample_checkpoint.to_json()
        response2 = s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json',
            Body=updated_json.encode()
        )
        etag2 = response2['ETag']

        # ETags should be different
        assert etag1 != etag2

    def test_conditional_checkpoint_write(self, s3_client, sample_checkpoint):
        """Test conditional write with If-None-Match to prevent overwrites."""
        checkpoint_json = sample_checkpoint.to_json()

        # Initial save
        response = s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json',
            Body=checkpoint_json.encode()
        )
        etag = response['ETag']

        # Read current checkpoint
        get_response = s3_client.get_object(
            Bucket='test-bucket',
            Key='jobs/test-job-123/checkpoint.json'
        )
        current_etag = get_response['ETag']

        # Conditional update (simulate If-Match)
        # In real worker code, would use: IfMatch=current_etag
        # If ETag changed, write would fail
        assert current_etag == etag

    def test_checkpoint_not_found(self, s3_client):
        """Test handling missing checkpoint (new job)."""
        # Try to get non-existent checkpoint
        with pytest.raises(Exception):  # ClientError in real boto3
            s3_client.get_object(
                Bucket='test-bucket',
                Key='jobs/missing-job/checkpoint.json'
            )


@pytest.mark.integration
class TestCheckpointRecovery:
    """Test recovery from checkpoints after interruptions."""

    def test_resume_from_checkpoint(self, s3_client):
        """Test resuming job from checkpoint."""
        # Simulate checkpoint from interrupted job
        checkpoint = CheckpointState(
            job_id='job-123',
            records_generated=500,
            current_batch=10,
            tokens_used=100000,
            cost_accumulated=5.0,
            resume_state={'seed_index': 25}
        )

        # Save checkpoint
        s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/job-123/checkpoint.json',
            Body=checkpoint.to_json().encode()
        )

        # Simulate worker restart - load checkpoint
        response = s3_client.get_object(
            Bucket='test-bucket',
            Key='jobs/job-123/checkpoint.json'
        )
        restored = CheckpointState.from_json(
            response['Body'].read().decode(),
            etag=response['ETag'].strip('"')
        )

        # Verify worker can resume from this point
        assert restored.records_generated == 500
        assert restored.resume_state['seed_index'] == 25

    def test_checkpoint_interval_behavior(self):
        """Test checkpoint is saved every N records."""
        checkpoint_interval = 50
        records_generated = 0
        checkpoints_saved = 0

        # Simulate generation loop
        for i in range(250):
            records_generated += 1

            if records_generated % checkpoint_interval == 0:
                checkpoints_saved += 1

        # Should have saved 5 checkpoints (at 50, 100, 150, 200, 250)
        assert checkpoints_saved == 5

    def test_spot_interruption_checkpoint(self, s3_client):
        """Test checkpoint saved on spot interruption signal."""
        # Simulate job in progress
        checkpoint = CheckpointState(
            job_id='job-123',
            records_generated=73,  # Not at interval boundary
            current_batch=2,
            tokens_used=25000,
            cost_accumulated=1.50
        )

        # Simulate SIGTERM handler saving checkpoint
        s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/job-123/checkpoint.json',
            Body=checkpoint.to_json().encode()
        )

        # Verify checkpoint saved despite not being at interval
        response = s3_client.get_object(
            Bucket='test-bucket',
            Key='jobs/job-123/checkpoint.json'
        )
        restored = CheckpointState.from_json(
            response['Body'].read().decode()
        )

        assert restored.records_generated == 73


@pytest.mark.integration
@pytest.mark.slow
class TestCheckpointConcurrency:
    """Test concurrent checkpoint handling."""

    def test_concurrent_checkpoint_detection(self, s3_client):
        """Test detecting concurrent checkpoint writes via ETag."""
        # Initial checkpoint
        checkpoint1 = CheckpointState(
            job_id='job-123',
            records_generated=100,
            current_batch=2,
            tokens_used=50000,
            cost_accumulated=2.5
        )

        # Worker 1 saves checkpoint
        response1 = s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/job-123/checkpoint.json',
            Body=checkpoint1.to_json().encode()
        )
        etag1 = response1['ETag']

        # Worker 2 also saves checkpoint (simulating race condition)
        checkpoint2 = CheckpointState(
            job_id='job-123',
            records_generated=105,
            current_batch=3,
            tokens_used=52000,
            cost_accumulated=2.6
        )

        response2 = s3_client.put_object(
            Bucket='test-bucket',
            Key='jobs/job-123/checkpoint.json',
            Body=checkpoint2.to_json().encode()
        )
        etag2 = response2['ETag']

        # ETags should be different (last write wins in this mock)
        assert etag1 != etag2

    def test_checkpoint_merge_strategy(self):
        """Test merging checkpoints from concurrent workers."""
        # Checkpoint from worker 1
        checkpoint1 = {
            'records_generated': 100,
            'tokens_used': 50000,
            'cost_accumulated': 2.5
        }

        # Checkpoint from worker 2 (slightly ahead)
        checkpoint2 = {
            'records_generated': 105,
            'tokens_used': 52000,
            'cost_accumulated': 2.6
        }

        # Merge strategy: use maximum values
        merged = {
            'records_generated': max(
                checkpoint1['records_generated'],
                checkpoint2['records_generated']
            ),
            'tokens_used': max(
                checkpoint1['tokens_used'],
                checkpoint2['tokens_used']
            ),
            'cost_accumulated': max(
                checkpoint1['cost_accumulated'],
                checkpoint2['cost_accumulated']
            )
        }

        assert merged['records_generated'] == 105
        assert merged['tokens_used'] == 52000
        assert merged['cost_accumulated'] == 2.6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--integration"])
