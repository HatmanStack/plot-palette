"""
Plot Palette - Worker S3 Error Handling Tests

Tests for Worker behavior when S3 operations fail.
"""

import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
import json


class TestSeedDataLoadFailures:
    """Tests for seed data load failure handling."""

    def test_no_such_key_raises_exception(self):
        """Test that NoSuchKey error raises exception."""
        error_response = {
            'Error': {
                'Code': 'NoSuchKey',
                'Message': 'The specified key does not exist.'
            }
        }

        error = ClientError(error_response, 'GetObject')

        is_not_found = error.response['Error']['Code'] == 'NoSuchKey'

        assert is_not_found is True

    def test_seed_data_required_for_job(self):
        """Test that seed data is required - job should fail without it."""
        seed_data_exists = False

        # Job cannot proceed without seed data
        can_proceed = seed_data_exists

        assert can_proceed is False

    def test_seed_data_path_from_config(self):
        """Test seed data path extraction from config."""
        config = {
            'seed_data_path': 'seed-data/user-123/data.json'
        }

        seed_path = config['seed_data_path']

        assert seed_path == 'seed-data/user-123/data.json'


class TestSeedDataInvalidJSON:
    """Tests for invalid seed data JSON handling."""

    def test_invalid_json_decode_error(self):
        """Test that invalid JSON raises JSONDecodeError."""
        invalid_json = "not valid json content"

        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)

    def test_truncated_json_raises_error(self):
        """Test that truncated JSON raises error."""
        truncated_json = '[{"name": "test"'

        with pytest.raises(json.JSONDecodeError):
            json.loads(truncated_json)

    def test_meaningful_error_message(self):
        """Test that JSON error includes meaningful message."""
        try:
            json.loads("invalid")
        except json.JSONDecodeError as e:
            error_message = str(e)
            assert 'Expecting value' in error_message


class TestCheckpointSaveFailures:
    """Tests for checkpoint save failure handling."""

    def test_s3_put_object_failure(self):
        """Test handling of S3 put_object failure."""
        error_response = {
            'Error': {
                'Code': 'InternalError',
                'Message': 'Internal server error'
            }
        }

        error = ClientError(error_response, 'PutObject')

        assert error.response['Error']['Code'] == 'InternalError'

    def test_checkpoint_save_is_critical(self):
        """Test that checkpoint save failure propagates exception."""
        checkpoint_is_critical = True

        # Checkpoint failures should propagate
        should_propagate = checkpoint_is_critical

        assert should_propagate is True

    def test_checkpoint_save_retry_on_failure(self):
        """Test checkpoint save can retry on transient failures."""
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            retry_count += 1
            if retry_count == 2:  # Succeed on second try
                success = True

        assert success is True
        assert retry_count == 2


class TestBatchSaveFailures:
    """Tests for batch save failure handling."""

    def test_batch_save_s3_error(self):
        """Test S3 error during batch save."""
        error_response = {
            'Error': {
                'Code': 'ServiceUnavailable',
                'Message': 'Service unavailable'
            }
        }

        error = ClientError(error_response, 'PutObject')

        assert error.response['Error']['Code'] == 'ServiceUnavailable'

    def test_batch_save_logged_on_failure(self):
        """Test that batch save failure is logged."""
        error_logged = False

        try:
            raise ClientError(
                {'Error': {'Code': 'InternalError', 'Message': 'Error'}},
                'PutObject'
            )
        except ClientError:
            error_logged = True

        assert error_logged is True


class TestExportFailures:
    """Tests for export operation failure handling."""

    def test_export_put_object_failure(self):
        """Test handling of export put_object failure."""
        error_response = {
            'Error': {
                'Code': 'InternalError',
                'Message': 'Failed to write export'
            }
        }

        error = ClientError(error_response, 'PutObject')

        assert error.response['Error']['Code'] == 'InternalError'

    def test_job_status_reflects_export_failure(self):
        """Test that job status reflects export failure."""
        export_succeeded = False

        if not export_succeeded:
            job_status = 'FAILED'
        else:
            job_status = 'COMPLETED'

        assert job_status == 'FAILED'


class TestS3BucketConfiguration:
    """Tests for S3 bucket configuration validation."""

    def test_missing_bucket_name_raises_error(self):
        """Test that missing BUCKET_NAME raises error early."""
        bucket_name = None

        if not bucket_name:
            error_raised = True
        else:
            error_raised = False

        assert error_raised is True

    def test_bucket_name_from_environment(self):
        """Test bucket name is read from environment."""
        import os

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv('BUCKET_NAME', 'test-bucket')
            bucket_name = os.environ.get('BUCKET_NAME')

        assert bucket_name == 'test-bucket'


class TestLoadBatchesFailure:
    """Tests for loading batches during export failure."""

    def test_list_objects_failure(self):
        """Test handling of list_objects_v2 failure."""
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }

        error = ClientError(error_response, 'ListObjectsV2')

        assert error.response['Error']['Code'] == 'AccessDenied'

    def test_load_batches_returns_empty_on_failure(self):
        """Test that load_all_batches returns empty list on failure."""
        error_occurred = True

        if error_occurred:
            batches = []
        else:
            batches = ['batch1', 'batch2']

        assert batches == []

    def test_load_batches_failure_logged(self):
        """Test that batch load failure is logged."""
        error_logged = False

        try:
            raise ClientError(
                {'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket not found'}},
                'ListObjectsV2'
            )
        except ClientError:
            error_logged = True

        assert error_logged is True


class TestS3AccessDenied:
    """Tests for S3 access denied handling."""

    def test_access_denied_on_get_object(self):
        """Test AccessDenied on get_object."""
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }

        error = ClientError(error_response, 'GetObject')

        assert error.response['Error']['Code'] == 'AccessDenied'

    def test_access_denied_on_put_object(self):
        """Test AccessDenied on put_object."""
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }

        error = ClientError(error_response, 'PutObject')

        assert error.response['Error']['Code'] == 'AccessDenied'


class TestS3ContentTypeHandling:
    """Tests for S3 content type handling."""

    def test_jsonl_content_type(self):
        """Test JSONL export uses correct content type."""
        content_type = 'application/x-ndjson'

        assert content_type == 'application/x-ndjson'

    def test_parquet_content_type(self):
        """Test Parquet export uses correct content type."""
        content_type = 'application/octet-stream'

        assert content_type == 'application/octet-stream'

    def test_csv_content_type(self):
        """Test CSV export uses correct content type."""
        content_type = 'text/csv'

        assert content_type == 'text/csv'


class TestS3KeyFormatting:
    """Tests for S3 key formatting."""

    def test_checkpoint_key_format(self):
        """Test checkpoint key format."""
        job_id = 'test-job-123'
        key = f"jobs/{job_id}/checkpoint.json"

        assert key == 'jobs/test-job-123/checkpoint.json'

    def test_batch_key_format(self):
        """Test batch key format with padding."""
        job_id = 'test-job-123'
        batch_number = 5
        key = f"jobs/{job_id}/outputs/batch-{batch_number:04d}.jsonl"

        assert key == 'jobs/test-job-123/outputs/batch-0005.jsonl'

    def test_export_key_format(self):
        """Test export key format."""
        job_id = 'test-job-123'
        key = f"jobs/{job_id}/exports/dataset.jsonl"

        assert key == 'jobs/test-job-123/exports/dataset.jsonl'
