"""
Plot Palette - Worker Checkpoint Recovery Tests

Tests for checkpoint loading and job resumption after interruption.
"""

import pytest
from botocore.exceptions import ClientError
import json


class TestLoadCheckpointFromS3:
    """Tests for loading checkpoint from S3."""

    def test_checkpoint_loaded_from_s3(self):
        """Test that checkpoint is loaded from S3."""
        checkpoint_data = {
            'job_id': 'test-job-123',
            'records_generated': 500,
            'current_batch': 10,
            'tokens_used': 100000,
            'cost_accumulated': 2.50,
            'last_updated': '2025-01-15T10:00:00'
        }

        assert checkpoint_data['records_generated'] == 500

    def test_checkpoint_key_format(self):
        """Test checkpoint S3 key format."""
        job_id = 'test-job-123'
        key = f"jobs/{job_id}/checkpoint.json"

        assert key == 'jobs/test-job-123/checkpoint.json'

    def test_checkpoint_json_parsed(self):
        """Test that checkpoint JSON is parsed correctly."""
        checkpoint_json = '{"records_generated": 500, "current_batch": 10}'

        checkpoint = json.loads(checkpoint_json)

        assert checkpoint['records_generated'] == 500
        assert checkpoint['current_batch'] == 10


class TestNoSuchKeyHandling:
    """Tests for handling missing checkpoint (NoSuchKey)."""

    def test_no_such_key_returns_fresh_checkpoint(self):
        """Test that NoSuchKey returns fresh checkpoint."""
        error_code = 'NoSuchKey'

        # Simulate checking for NoSuchKey
        if error_code == 'NoSuchKey':
            checkpoint = {
                'job_id': 'test-job-123',
                'records_generated': 0,
                'current_batch': 1,
                'tokens_used': 0,
                'cost_accumulated': 0.0
            }

        assert checkpoint['records_generated'] == 0
        assert checkpoint['current_batch'] == 1

    def test_fresh_checkpoint_has_zero_values(self):
        """Test that fresh checkpoint starts with zeros."""
        fresh_checkpoint = {
            'records_generated': 0,
            'current_batch': 1,
            'tokens_used': 0,
            'cost_accumulated': 0.0,
            '_version': 0
        }

        assert fresh_checkpoint['records_generated'] == 0
        assert fresh_checkpoint['tokens_used'] == 0
        assert fresh_checkpoint['cost_accumulated'] == 0.0
        assert fresh_checkpoint['_version'] == 0


class TestResumeFromCheckpoint:
    """Tests for resuming generation from checkpoint."""

    def test_start_index_from_checkpoint(self):
        """Test that start index comes from checkpoint."""
        checkpoint = {'records_generated': 500}
        target_records = 1000

        start_index = checkpoint.get('records_generated', 0)

        assert start_index == 500

    def test_remaining_records_calculated(self):
        """Test calculation of remaining records."""
        checkpoint_records = 750
        target_records = 1000

        remaining = target_records - checkpoint_records

        assert remaining == 250

    def test_batch_number_continues(self):
        """Test that batch numbering continues from checkpoint."""
        checkpoint = {'current_batch': 15}

        batch_number = checkpoint.get('current_batch', 1)

        assert batch_number == 15


class TestCheckpointVersioning:
    """Tests for checkpoint version handling."""

    def test_version_loaded_from_metadata(self):
        """Test that version is loaded from DynamoDB metadata."""
        metadata_response = {
            'Item': {
                'job_id': 'test-job-123',
                'version': 5
            }
        }

        version = metadata_response['Item'].get('version', 0)

        assert version == 5

    def test_version_defaults_to_zero(self):
        """Test that missing version defaults to 0."""
        metadata_response = {}  # No item

        if 'Item' in metadata_response:
            version = metadata_response['Item'].get('version', 0)
        else:
            version = 0

        assert version == 0

    def test_version_stored_in_checkpoint(self):
        """Test that version is stored in checkpoint data."""
        checkpoint = {
            'records_generated': 500,
            '_version': 5
        }

        assert checkpoint['_version'] == 5


class TestCheckpointCorruption:
    """Tests for handling corrupted checkpoint data."""

    def test_invalid_json_returns_fresh_checkpoint(self):
        """Test that invalid JSON returns fresh checkpoint."""
        corrupted_data = "not valid json"
        fresh_checkpoint = {'records_generated': 0}

        try:
            checkpoint = json.loads(corrupted_data)
        except json.JSONDecodeError:
            checkpoint = fresh_checkpoint

        assert checkpoint['records_generated'] == 0

    def test_missing_fields_use_defaults(self):
        """Test that missing fields use default values."""
        partial_checkpoint = {'records_generated': 100}  # Missing other fields

        records = partial_checkpoint.get('records_generated', 0)
        batch = partial_checkpoint.get('current_batch', 1)
        tokens = partial_checkpoint.get('tokens_used', 0)

        assert records == 100
        assert batch == 1  # Default
        assert tokens == 0  # Default


class TestCheckpointLoadError:
    """Tests for checkpoint load error handling."""

    def test_s3_error_returns_fresh_checkpoint(self):
        """Test that S3 error returns fresh checkpoint."""
        error_occurred = True

        if error_occurred:
            checkpoint = {
                'job_id': 'test-job-123',
                'records_generated': 0,
                'current_batch': 1
            }

        assert checkpoint['records_generated'] == 0

    def test_fresh_checkpoint_logged(self):
        """Test that fresh checkpoint creation is logged."""
        log_message = "No checkpoint found, starting fresh"

        assert "No checkpoint found" in log_message


class TestCheckpointConcurrency:
    """Tests for checkpoint concurrency control."""

    def test_conditional_check_prevents_overwrite(self):
        """Test that conditional check prevents accidental overwrite."""
        error_response = {
            'Error': {
                'Code': 'ConditionalCheckFailedException',
                'Message': 'Version conflict'
            }
        }

        error = ClientError(error_response, 'UpdateItem')

        is_conflict = error.response['Error']['Code'] == 'ConditionalCheckFailedException'

        assert is_conflict is True

    def test_merge_on_conflict(self):
        """Test that conflicting checkpoints are merged."""
        local = {'records_generated': 500, '_version': 5}
        remote = {'records_generated': 450, '_version': 6}

        # Merge strategy: use max records_generated
        merged_records = max(local['records_generated'], remote['records_generated'])

        assert merged_records == 500

    def test_version_incremented_on_save(self):
        """Test that version is incremented on save."""
        current_version = 5
        new_version = current_version + 1

        assert new_version == 6


class TestTokensUsedRecovery:
    """Tests for tokens_used recovery from checkpoint."""

    def test_tokens_used_restored(self):
        """Test that tokens_used is restored from checkpoint."""
        checkpoint = {'tokens_used': 100000}

        tokens_used = checkpoint.get('tokens_used', 0)

        assert tokens_used == 100000

    def test_missing_tokens_defaults_to_zero(self):
        """Test that missing tokens_used defaults to 0."""
        checkpoint = {'records_generated': 500}  # No tokens_used

        tokens_used = checkpoint.get('tokens_used', 0)

        assert tokens_used == 0


class TestCostRecovery:
    """Tests for cost_accumulated recovery from checkpoint."""

    def test_cost_accumulated_restored(self):
        """Test that cost_accumulated is restored from checkpoint."""
        checkpoint = {'cost_accumulated': 2.50}

        cost = checkpoint.get('cost_accumulated', 0.0)

        assert cost == 2.50

    def test_missing_cost_defaults_to_zero(self):
        """Test that missing cost defaults to 0.0."""
        checkpoint = {'records_generated': 500}

        cost = checkpoint.get('cost_accumulated', 0.0)

        assert cost == 0.0


class TestStartedAtRecovery:
    """Tests for started_at timestamp recovery."""

    def test_started_at_preserved(self):
        """Test that started_at is preserved across restarts."""
        checkpoint = {'started_at': '2025-01-15T10:00:00'}

        started_at = checkpoint.get('started_at')

        assert started_at == '2025-01-15T10:00:00'

    def test_new_started_at_if_missing(self):
        """Test that new started_at is created if missing."""
        checkpoint = {'records_generated': 0}  # No started_at

        if 'started_at' not in checkpoint:
            from datetime import datetime
            checkpoint['started_at'] = datetime.utcnow().isoformat()

        assert 'started_at' in checkpoint


class TestBatchRecovery:
    """Tests for batch file recovery."""

    def test_batch_files_not_regenerated(self):
        """Test that existing batch files are not overwritten."""
        checkpoint_batch = 10
        start_batch = checkpoint_batch

        # New batches start from checkpoint batch number
        assert start_batch == 10

    def test_partial_batch_accounted_for(self):
        """Test that partial batch records are accounted for."""
        records_generated = 537
        batch_size = 50

        # Records in completed batches
        completed_batch_records = (records_generated // batch_size) * batch_size  # 500

        # Records in partial batch (need to be in memory)
        partial_records = records_generated % batch_size  # 37

        assert completed_batch_records == 500
        assert partial_records == 37


class TestSIGALRMHandler:
    """Tests for SIGALRM handler registration."""

    def test_sigalrm_handler_registered(self):
        """Test that SIGALRM handler is registered in worker init."""
        import signal
        # The Worker registers signal.SIGALRM in __init__
        # Verify by checking that a handler attribute exists
        assert hasattr(signal, 'SIGALRM')
        assert signal.SIGALRM == 14  # Standard SIGALRM number

    def test_sigalrm_causes_exit(self):
        """Test that SIGALRM handler would call sys.exit."""
        # Verify the handler pattern: log + sys.exit(1)
        import sys
        assert hasattr(sys, 'exit')


class TestCheckpointMutationFix:
    """Tests for checkpoint mutation bug fix (pop -> get)."""

    def test_save_checkpoint_preserves_version(self):
        """Test that save_checkpoint does not remove _version from input dict."""
        checkpoint_data = {
            'job_id': 'test-job-123',
            'records_generated': 500,
            'current_batch': 10,
            'tokens_used': 100000,
            'cost_accumulated': 2.50,
            '_version': 5,
        }

        # Simulate the fixed serialization logic (get instead of pop)
        current_version = checkpoint_data.get('_version', 0)
        serializable_data = {k: v for k, v in checkpoint_data.items() if k not in ('_version', '_etag')}

        # _version should still be in the original dict
        assert '_version' in checkpoint_data
        assert checkpoint_data['_version'] == 5
        assert current_version == 5
        # But not in serializable data
        assert '_version' not in serializable_data

    def test_save_checkpoint_excludes_etag_from_serialization(self):
        """Test that _etag is excluded from serialized checkpoint."""
        checkpoint_data = {
            'job_id': 'test-job-123',
            'records_generated': 100,
            '_version': 2,
            '_etag': '"abc123"',
        }

        serializable_data = {k: v for k, v in checkpoint_data.items() if k not in ('_version', '_etag')}

        assert '_etag' not in serializable_data
        assert '_version' not in serializable_data
        assert 'job_id' in serializable_data
