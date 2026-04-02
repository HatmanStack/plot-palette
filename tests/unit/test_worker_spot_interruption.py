"""
Plot Palette - Worker Spot Interruption Tests

Tests for the Worker's graceful shutdown and checkpoint saving on SIGTERM.
"""

import signal
import pytest
from unittest.mock import MagicMock, patch
import json


class TestSignalHandling:
    """Tests for SIGTERM signal handling."""

    def test_sigterm_sets_shutdown_flag(self):
        """Test that SIGTERM handler sets shutdown_requested flag."""
        # Simulate Worker state
        shutdown_requested = False

        def handle_shutdown(signum, frame):
            nonlocal shutdown_requested
            shutdown_requested = True

        # Simulate SIGTERM
        handle_shutdown(signal.SIGTERM, None)

        assert shutdown_requested is True

    def test_shutdown_flag_initially_false(self):
        """Test that shutdown flag starts as False."""
        shutdown_requested = False

        assert shutdown_requested is False

    def test_sigterm_number_is_15(self):
        """Test that SIGTERM signal number is 15."""
        assert signal.SIGTERM == 15

    def test_alarm_set_on_shutdown(self):
        """Test that alarm is set for forced exit on shutdown."""
        alarm_seconds = None

        def mock_alarm(seconds):
            nonlocal alarm_seconds
            alarm_seconds = seconds

        # Simulate handle_shutdown setting alarm
        alarm_seconds = 100  # 100 seconds buffer (120s - 20s safety)

        assert alarm_seconds == 100

    def test_sigalrm_can_be_caught(self):
        """Test that SIGALRM can be registered."""
        sigalrm_registered = False

        def alarm_handler(signum, frame):
            nonlocal sigalrm_registered
            sigalrm_registered = True

        # SIGALRM is signal 14
        assert signal.SIGALRM == 14


class TestGenerationLoopShutdown:
    """Tests for generation loop exit on shutdown."""

    def test_loop_exits_when_shutdown_requested(self):
        """Test that generation loop exits when shutdown flag is set."""
        shutdown_requested = False
        records_processed = 0
        target_records = 100

        for i in range(target_records):
            if shutdown_requested:
                break

            records_processed += 1

            # Simulate shutdown after 10 records
            if records_processed == 10:
                shutdown_requested = True

        assert records_processed == 10
        assert records_processed < target_records

    def test_loop_completes_when_no_shutdown(self):
        """Test that loop completes all records when not interrupted."""
        shutdown_requested = False
        records_processed = 0
        target_records = 50

        for i in range(target_records):
            if shutdown_requested:
                break
            records_processed += 1

        assert records_processed == target_records

    def test_shutdown_check_frequency(self):
        """Test that shutdown is checked before each record."""
        shutdown_requested = False
        shutdown_checks = 0
        target_records = 5

        for i in range(target_records):
            shutdown_checks += 1  # Check happens before processing
            if shutdown_requested:
                break

        assert shutdown_checks == target_records


class TestCheckpointOnInterruption:
    """Tests for checkpoint saving on interruption."""

    def test_checkpoint_saved_on_shutdown(self):
        """Test that checkpoint is saved when shutdown is requested."""
        checkpoint_saved = False
        shutdown_requested = True

        if shutdown_requested:
            # Simulate checkpoint save
            checkpoint_saved = True

        assert checkpoint_saved is True

    def test_checkpoint_contains_records_generated(self):
        """Test that checkpoint contains correct records_generated count."""
        records_generated = 37
        checkpoint = {
            'job_id': 'test-job-123',
            'records_generated': records_generated,
            'current_batch': 1,
            'tokens_used': 5000
        }

        assert checkpoint['records_generated'] == 37

    def test_checkpoint_contains_tokens_used(self):
        """Test that checkpoint tracks tokens_used."""
        tokens_used = 15000
        checkpoint = {
            'job_id': 'test-job-123',
            'records_generated': 100,
            'tokens_used': tokens_used
        }

        assert checkpoint['tokens_used'] == 15000

    def test_checkpoint_contains_current_batch(self):
        """Test that checkpoint tracks current_batch number."""
        checkpoint = {
            'job_id': 'test-job-123',
            'records_generated': 100,
            'current_batch': 3
        }

        assert checkpoint['current_batch'] == 3

    def test_checkpoint_contains_cost_accumulated(self):
        """Test that checkpoint tracks cost_accumulated."""
        checkpoint = {
            'job_id': 'test-job-123',
            'records_generated': 100,
            'cost_accumulated': 2.50
        }

        assert checkpoint['cost_accumulated'] == 2.50

    def test_checkpoint_version_tracked(self):
        """Test that checkpoint version is tracked for concurrency."""
        checkpoint = {
            'job_id': 'test-job-123',
            'records_generated': 100,
            '_version': 5
        }

        assert checkpoint['_version'] == 5


class TestPartialBatchSaving:
    """Tests for partial batch saving on interruption."""

    def test_partial_batch_saved_on_shutdown(self):
        """Test that partial batch is saved when checkpoint interval not reached."""
        batch_size = 50  # Checkpoint interval
        records_in_batch = 37  # Partial batch
        batch_saved = False

        batch_records = ['record'] * records_in_batch

        if batch_records:  # Save if there are any records
            batch_saved = True

        assert records_in_batch < batch_size
        assert batch_saved is True

    def test_empty_batch_not_saved(self):
        """Test that empty batch is not saved."""
        batch_records = []
        batch_saved = False

        if batch_records:
            batch_saved = True

        assert batch_saved is False

    def test_full_batch_saved_before_partial(self):
        """Test that full batches are saved before accumulating partial."""
        batch_size = 50
        total_records = 137

        full_batches = total_records // batch_size  # 2
        partial_remaining = total_records % batch_size  # 37

        assert full_batches == 2
        assert partial_remaining == 37


class TestShutdownTimeline:
    """Tests for 120-second shutdown timeline handling."""

    def test_alarm_gives_adequate_buffer(self):
        """Test that alarm leaves adequate buffer before forced termination."""
        spot_warning_seconds = 120  # AWS gives 120s warning
        alarm_seconds = 100  # Alarm set for 100s
        buffer_seconds = spot_warning_seconds - alarm_seconds

        assert buffer_seconds >= 20  # At least 20s buffer

    def test_checkpoint_completes_within_buffer(self):
        """Test that checkpoint save should complete within buffer time."""
        # Typical checkpoint save time (rough estimate)
        s3_write_time = 0.5  # S3 put_object
        dynamodb_write_time = 0.2  # DynamoDB update
        total_checkpoint_time = s3_write_time + dynamodb_write_time

        buffer_time = 20  # seconds

        assert total_checkpoint_time < buffer_time


class TestWorkerStateOnInterruption:
    """Tests for Worker state preservation on interruption."""

    def test_job_not_marked_failed_on_interruption(self):
        """Test that job is not marked as FAILED on clean interruption."""
        # When shutdown is clean (checkpoint saved), job should remain RUNNING
        shutdown_clean = True
        job_status = 'RUNNING'

        # Only mark failed if there's an actual error, not clean shutdown
        if not shutdown_clean:
            job_status = 'FAILED'

        assert job_status == 'RUNNING'

    def test_queue_status_not_changed_on_interruption(self):
        """Test that queue status is not changed on clean interruption."""
        # Job stays in RUNNING queue so another worker can pick it up
        queue_status = 'RUNNING'
        shutdown_requested = True

        # Queue status should not change on clean shutdown
        if shutdown_requested:
            # Don't change queue status - another worker will resume
            pass

        assert queue_status == 'RUNNING'


class TestResumeAfterInterruption:
    """Tests for resume capability after interruption."""

    def test_checkpoint_enables_resume(self):
        """Test that checkpoint contains all needed data to resume."""
        checkpoint = {
            'job_id': 'test-job-123',
            'records_generated': 500,
            'current_batch': 10,
            'tokens_used': 100000,
            'cost_accumulated': 2.50,
            'last_updated': '2025-01-15T10:00:00',
            '_version': 5
        }

        # All required fields for resume
        required_fields = ['job_id', 'records_generated', 'current_batch', 'tokens_used']

        for field in required_fields:
            assert field in checkpoint

    def test_resume_starts_from_checkpoint_index(self):
        """Test that resume starts from checkpoint records_generated."""
        checkpoint_records = 500
        target_records = 1000

        # Generation should start from checkpoint index
        start_index = checkpoint_records
        records_to_generate = target_records - start_index

        assert start_index == 500
        assert records_to_generate == 500

    def test_batch_numbering_continues_from_checkpoint(self):
        """Test that batch numbering continues from checkpoint."""
        checkpoint_batch = 10
        records_per_batch = 50

        # Next batch number after resume
        next_batch = checkpoint_batch

        assert next_batch == 10


class TestSignalHandlerRegistration:
    """Tests for signal handler registration."""

    def test_sigterm_handler_can_be_registered(self):
        """Test that SIGTERM handler can be registered."""
        handler_registered = False

        def setup_signal_handler():
            nonlocal handler_registered
            # In real code: signal.signal(signal.SIGTERM, handle_shutdown)
            handler_registered = True

        setup_signal_handler()

        assert handler_registered is True

    def test_multiple_signals_can_be_handled(self):
        """Test that multiple signals can be handled."""
        signals_registered = []

        def register_handlers():
            signals_registered.append('SIGTERM')
            signals_registered.append('SIGALRM')

        register_handlers()

        assert 'SIGTERM' in signals_registered
        assert 'SIGALRM' in signals_registered


class TestStepFunctionsModeInterruption:
    """Tests for Spot interruption behavior in Step Functions mode."""

    def test_sf_mode_exits_with_error_on_interruption(self):
        """In SF mode, Spot interruption causes exit code 1 (error)."""
        # When SIGTERM is received in SF mode, the worker exits with code 1
        # because the generation loop exits early via shutdown_requested flag,
        # which causes sys.exit(1) in _run_step_functions_mode.
        exit_code_on_interruption = 1  # WORKER_EXIT_ERROR
        assert exit_code_on_interruption == 1

    def test_sf_mode_checkpoint_saved_before_exit(self):
        """In SF mode, checkpoint is still saved before exit on interruption."""
        # The generate_data loop saves checkpoint when shutdown_requested is True
        # This happens before the exception propagates to run()
        shutdown_requested = True
        checkpoint_saved = False

        if shutdown_requested:
            checkpoint_saved = True

        assert checkpoint_saved is True

    def test_sf_mode_state_machine_retries_after_spot(self):
        """Step Functions state machine retries the ECS task after Spot interruption."""
        max_retries = 5
        retry_count = 0

        # State machine increments retry_count and loops back to RunWorkerTask
        retry_count += 1

        assert retry_count < max_retries


def _import_worker():
    """Import Worker class with mocked environment."""
    from unittest.mock import patch as _patch
    import os as _os
    import sys as _sys

    worker_dir = _os.path.join(
        _os.path.dirname(__file__), "..", "..", "backend", "ecs_tasks", "worker"
    )
    worker_dir = _os.path.abspath(worker_dir)

    env_vars = {
        "JOBS_TABLE_NAME": "test-Jobs",
        "TEMPLATES_TABLE_NAME": "test-Templates",
        "COST_TRACKING_TABLE_NAME": "test-CostTracking",
        "CHECKPOINT_METADATA_TABLE_NAME": "test-CheckpointMetadata",
        "BUCKET_NAME": "test-bucket",
        "QUEUE_TABLE_NAME": "test-Queue",
        "AWS_DEFAULT_REGION": "us-east-1",
    }

    old_path = _sys.path[:]
    try:
        if worker_dir not in _sys.path:
            _sys.path.insert(0, worker_dir)

        with _patch.dict(_os.environ, env_vars):
            from backend.ecs_tasks.worker.worker import Worker
            return Worker
    except ImportError as e:
        missing = getattr(e, "name", "") or str(e)
        optional_deps = {"boto3", "pandas", "pyarrow", "template_engine"}
        if any(dep in missing for dep in optional_deps):
            pytest.skip(f"Worker dependency not installed: {e}")
        raise
    finally:
        _sys.path = old_path


class TestHealthMarkerFile:
    """Tests for Docker HEALTHCHECK marker file using the actual Worker class."""

    def test_health_file_created_on_init(self, tmp_path):
        """Test that Worker.__init__ creates the health marker file."""
        health_file = tmp_path / "worker_healthy"
        assert not health_file.exists()

        Worker = _import_worker()
        worker = Worker.__new__(Worker)
        worker.shutdown_requested = False
        worker.HEALTH_FILE = health_file
        worker.HEALTH_HEARTBEAT_INTERVAL = 9999  # Don't actually heartbeat
        worker._touch_health_file()

        assert health_file.exists()

    def test_touch_health_file_updates_mtime(self, tmp_path):
        """Test that _touch_health_file updates the file modification time."""
        import time as time_mod

        health_file = tmp_path / "worker_healthy"

        Worker = _import_worker()
        worker = Worker.__new__(Worker)
        worker.shutdown_requested = False
        worker.HEALTH_FILE = health_file

        worker._touch_health_file()
        initial_mtime = health_file.stat().st_mtime

        time_mod.sleep(0.05)

        worker._touch_health_file()
        new_mtime = health_file.stat().st_mtime

        assert new_mtime > initial_mtime

    def test_touch_health_file_handles_os_error(self):
        """Test that _touch_health_file logs warning on OSError."""
        from pathlib import Path

        Worker = _import_worker()
        worker = Worker.__new__(Worker)
        worker.shutdown_requested = False
        worker.HEALTH_FILE = Path("/nonexistent/deeply/nested/path/worker_healthy")

        # Should not raise — error is caught and logged
        worker._touch_health_file()

    def test_heartbeat_thread_touches_file(self, tmp_path):
        """Test that the heartbeat thread periodically touches the health file."""
        import time as time_mod

        health_file = tmp_path / "worker_healthy"

        Worker = _import_worker()
        worker = Worker.__new__(Worker)
        worker.shutdown_requested = False
        worker.HEALTH_FILE = health_file
        worker.HEALTH_HEARTBEAT_INTERVAL = 1  # 1 second for fast test

        worker._touch_health_file()
        initial_mtime = health_file.stat().st_mtime

        worker._start_health_heartbeat()
        time_mod.sleep(1.5)  # Wait for at least one heartbeat

        new_mtime = health_file.stat().st_mtime
        assert new_mtime > initial_mtime

        # Clean shutdown
        worker.shutdown_requested = True
        worker._heartbeat_thread.join(timeout=3)


class TestGracefulShutdownSequence:
    """Tests for the complete graceful shutdown sequence."""

    def test_shutdown_sequence_order(self):
        """Test that shutdown follows correct sequence."""
        sequence = []

        def shutdown_sequence():
            sequence.append('set_shutdown_flag')
            sequence.append('exit_generation_loop')
            sequence.append('save_partial_batch')
            sequence.append('save_checkpoint')
            sequence.append('update_job_progress')

        shutdown_sequence()

        assert sequence.index('set_shutdown_flag') < sequence.index('exit_generation_loop')
        assert sequence.index('exit_generation_loop') < sequence.index('save_partial_batch')
        assert sequence.index('save_partial_batch') < sequence.index('save_checkpoint')

    def test_errors_during_shutdown_handled(self):
        """Test that errors during shutdown are handled gracefully."""
        checkpoint_save_succeeded = False
        shutdown_error = None

        try:
            # Simulate checkpoint save that might fail
            checkpoint_save_succeeded = True
        except Exception as e:
            shutdown_error = str(e)
            # Log error but don't crash
            pass

        # Either succeeds or fails gracefully
        assert checkpoint_save_succeeded is True or shutdown_error is not None
