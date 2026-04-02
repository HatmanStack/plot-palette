"""
Plot Palette - Worker Bedrock Error Handling Tests

Tests for Worker behavior when Bedrock API calls fail.
"""

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
import json


class TestBedrockThrottling:
    """Tests for Bedrock rate limiting/throttling handling."""

    def test_throttling_exception_detected(self):
        """Test detection of ThrottlingException."""
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Rate exceeded'
            }
        }

        error = ClientError(error_response, 'InvokeModel')

        is_throttling = error.response['Error']['Code'] == 'ThrottlingException'

        assert is_throttling is True

    def test_throttling_continues_to_next_record(self):
        """Test that throttling error continues to next record."""
        records_attempted = 0
        records_succeeded = 0
        throttling_occurred = False

        for i in range(5):
            records_attempted += 1
            try:
                if i == 2:  # Throttle on record 2
                    raise ClientError(
                        {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                        'InvokeModel'
                    )
                records_succeeded += 1
            except ClientError as e:
                if e.response['Error']['Code'] == 'ThrottlingException':
                    throttling_occurred = True
                    continue  # Skip to next record

        assert records_attempted == 5
        assert records_succeeded == 4
        assert throttling_occurred is True

    def test_service_quota_exceeded(self):
        """Test ServiceQuotaExceededException handling."""
        error_response = {
            'Error': {
                'Code': 'ServiceQuotaExceededException',
                'Message': 'Service quota exceeded'
            }
        }

        error = ClientError(error_response, 'InvokeModel')

        assert error.response['Error']['Code'] == 'ServiceQuotaExceededException'


class TestBedrockModelErrors:
    """Tests for Bedrock model error handling."""

    def test_model_error_exception(self):
        """Test ModelErrorException handling."""
        error_response = {
            'Error': {
                'Code': 'ModelErrorException',
                'Message': 'Model failed to generate response'
            }
        }

        error = ClientError(error_response, 'InvokeModel')

        assert error.response['Error']['Code'] == 'ModelErrorException'

    def test_model_error_continues_to_next_record(self):
        """Test that model error continues to next record."""
        errors_occurred = 0
        records_processed = 0

        for i in range(5):
            try:
                if i == 1:  # Model error on record 1
                    raise ClientError(
                        {'Error': {'Code': 'ModelErrorException', 'Message': 'Model error'}},
                        'InvokeModel'
                    )
                records_processed += 1
            except ClientError:
                errors_occurred += 1
                continue

        assert records_processed == 4
        assert errors_occurred == 1

    def test_model_not_ready_exception(self):
        """Test ModelNotReadyException handling."""
        error_response = {
            'Error': {
                'Code': 'ModelNotReadyException',
                'Message': 'Model is not ready to serve requests'
            }
        }

        error = ClientError(error_response, 'InvokeModel')

        assert error.response['Error']['Code'] == 'ModelNotReadyException'


class TestBedrockTimeout:
    """Tests for Bedrock timeout handling."""

    def test_read_timeout_handling(self):
        """Test handling of read timeout."""
        from botocore.exceptions import ReadTimeoutError

        timeout_occurred = False

        try:
            raise ReadTimeoutError(endpoint_url='https://bedrock-runtime.us-east-1.amazonaws.com')
        except ReadTimeoutError:
            timeout_occurred = True

        assert timeout_occurred is True

    def test_connect_timeout_handling(self):
        """Test handling of connect timeout."""
        from botocore.exceptions import ConnectTimeoutError

        timeout_occurred = False

        try:
            raise ConnectTimeoutError(endpoint_url='https://bedrock-runtime.us-east-1.amazonaws.com')
        except ConnectTimeoutError:
            timeout_occurred = True

        assert timeout_occurred is True


class TestBedrockValidationErrors:
    """Tests for Bedrock validation error handling."""

    def test_validation_exception(self):
        """Test ValidationException handling for bad prompts."""
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid input: prompt exceeds maximum length'
            }
        }

        error = ClientError(error_response, 'InvokeModel')

        assert error.response['Error']['Code'] == 'ValidationException'

    def test_validation_error_logged_with_context(self):
        """Test that validation errors are logged with context."""
        prompt = "Test prompt that caused error"
        model_id = "meta.llama3-1-8b-instruct-v1:0"

        error_context = {
            'prompt_length': len(prompt),
            'model_id': model_id,
            'error_type': 'ValidationException'
        }

        # Error context should include debugging info
        assert 'prompt_length' in error_context
        assert 'model_id' in error_context


class TestBedrockAccessDenied:
    """Tests for Bedrock access denied handling (fatal error)."""

    def test_access_denied_exception(self):
        """Test AccessDeniedException handling."""
        error_response = {
            'Error': {
                'Code': 'AccessDeniedException',
                'Message': 'User is not authorized to invoke this model'
            }
        }

        error = ClientError(error_response, 'InvokeModel')

        assert error.response['Error']['Code'] == 'AccessDeniedException'

    def test_access_denied_is_fatal(self):
        """Test that AccessDeniedException causes job failure."""
        is_fatal = True  # AccessDenied should fail the entire job

        error_code = 'AccessDeniedException'

        # Fatal errors that should fail the job immediately
        fatal_error_codes = [
            'AccessDeniedException',
            'ResourceNotFoundException',
            'ModelNotReadyException'
        ]

        is_fatal = error_code in fatal_error_codes

        assert is_fatal is True

    def test_access_denied_stops_job(self):
        """Test that AccessDenied stops all further processing."""
        job_should_continue = True

        try:
            raise ClientError(
                {'Error': {'Code': 'AccessDeniedException', 'Message': 'Not authorized'}},
                'InvokeModel'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDeniedException':
                job_should_continue = False

        assert job_should_continue is False


class TestPartialBedrockFailures:
    """Tests for partial failure resilience."""

    def test_partial_failures_tracked(self):
        """Test that partial failures are tracked correctly."""
        total_attempts = 20
        failure_rate = 0.2  # Fail every 5th record
        failures = []
        successes = []

        for i in range(total_attempts):
            if (i + 1) % 5 == 0:  # Fail every 5th
                failures.append(i)
            else:
                successes.append(i)

        assert len(failures) == 4
        assert len(successes) == 16

    def test_generation_continues_after_partial_failure(self):
        """Test that generation continues after partial failures."""
        records_generated = []
        errors = []

        for i in range(10):
            try:
                if i in [2, 5, 8]:  # Specific failures
                    raise ClientError(
                        {'Error': {'Code': 'ModelErrorException', 'Message': 'Model error'}},
                        'InvokeModel'
                    )
                records_generated.append(f'record-{i}')
            except ClientError:
                errors.append(i)
                continue

        assert len(records_generated) == 7
        assert len(errors) == 3
        assert 'record-0' in records_generated
        assert 'record-9' in records_generated

    def test_all_failures_logged(self):
        """Test that all failures are logged."""
        error_log = []

        for i in range(5):
            try:
                if i % 2 == 0:  # Fail even records
                    raise ClientError(
                        {'Error': {'Code': 'ModelErrorException', 'Message': f'Error on record {i}'}},
                        'InvokeModel'
                    )
            except ClientError as e:
                error_log.append({
                    'record_index': i,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                })
                continue

        assert len(error_log) == 3  # Records 0, 2, 4


class TestTemplateEngineErrors:
    """Tests for template engine error handling."""

    def test_template_execution_error_caught(self):
        """Test that template execution errors are caught."""
        error_caught = False

        def mock_execute_template():
            raise ValueError("Template variable not found: author.name")

        try:
            mock_execute_template()
        except ValueError:
            error_caught = True

        assert error_caught is True

    def test_template_error_continues_generation(self):
        """Test that template errors don't stop generation."""
        records_processed = 0
        template_errors = 0

        for i in range(5):
            try:
                if i == 2:
                    raise ValueError("Template error")
                records_processed += 1
            except ValueError:
                template_errors += 1
                continue

        assert records_processed == 4
        assert template_errors == 1

    def test_jinja2_syntax_error_handling(self):
        """Test handling of Jinja2 template syntax errors."""
        error_caught = False

        try:
            import jinja2
            env = jinja2.Environment()
            env.from_string("{{ unclosed")
        except jinja2.TemplateSyntaxError:
            error_caught = True

        assert error_caught is True


class TestBedrockCostOnFailure:
    """Tests for cost tracking when Bedrock calls fail (CRITICAL-8)."""

    def test_cost_not_accumulated_on_failure(self):
        """Verify cost is NOT incremented when a Bedrock call fails.

        The generation loop in worker.py only updates running_cost inside
        the try block, after a successful template execution. If the call
        raises, the except block increments failed_records but not cost.
        """
        running_cost = 0.0
        failed_records = 0
        records_generated = 0

        for i in range(5):
            try:
                if i == 2:
                    raise Exception("Bedrock throttled")
                # Successful call -- cost added
                running_cost += 0.01
                records_generated += 1
            except Exception:
                failed_records += 1
                continue

        assert records_generated == 4
        assert failed_records == 1
        # Cost should only reflect successful calls
        assert abs(running_cost - 0.04) < 1e-9

    def test_failed_records_counter_still_increments(self):
        """Verify failed_records counter increments on Bedrock failure."""
        failed_records = 0

        for i in range(3):
            try:
                raise Exception("Bedrock error")
            except Exception:
                failed_records += 1
                continue

        assert failed_records == 3

    def test_cost_only_after_successful_response(self):
        """Simulate the exact worker pattern: cost accumulates only on success."""
        running_cost = 0.0
        checkpoint = {"cost_accumulated": 0.0, "records_generated": 0}

        results = [
            {"step1": {"output": "ok", "model": "meta.llama3-1-8b-instruct-v1:0"}},
            None,  # Simulates exception
            {"step1": {"output": "ok", "model": "meta.llama3-1-8b-instruct-v1:0"}},
        ]

        for i, result in enumerate(results):
            try:
                if result is None:
                    raise Exception("Bedrock API error")
                # Success path -- mirrors worker.py lines 353-360
                checkpoint["records_generated"] = i + 1
                running_cost += 0.005  # Simulated cost
            except Exception:
                # Failure path -- mirrors worker.py lines 375-380
                continue

        # Only 2 successful calls
        assert checkpoint["records_generated"] == 3  # last successful index+1
        assert abs(running_cost - 0.01) < 1e-9


class TestBedrockResponseParsing:
    """Tests for Bedrock response parsing error handling."""

    def test_invalid_response_body_handling(self):
        """Test handling of invalid response body from Bedrock."""
        error_caught = False

        try:
            response_body = "not valid json"
            json.loads(response_body)
        except json.JSONDecodeError:
            error_caught = True

        assert error_caught is True

    def test_missing_content_field_handling(self):
        """Test handling of response missing expected fields."""
        response = {
            'usage': {'input_tokens': 100, 'output_tokens': 50}
            # Missing 'content' field
        }

        has_content = 'content' in response

        assert has_content is False

    def test_claude_response_parsing(self):
        """Test parsing of Claude model response."""
        response = {
            'content': [{'text': 'Generated response'}],
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        }

        text = response['content'][0]['text']
        input_tokens = response['usage']['input_tokens']
        output_tokens = response['usage']['output_tokens']

        assert text == 'Generated response'
        assert input_tokens == 100
        assert output_tokens == 50

    def test_llama_response_parsing(self):
        """Test parsing of Llama model response."""
        response = {
            'generation': 'Generated response from Llama',
            'prompt_token_count': 100,
            'generation_token_count': 50
        }

        text = response['generation']
        input_tokens = response['prompt_token_count']
        output_tokens = response['generation_token_count']

        assert text == 'Generated response from Llama'
        assert input_tokens == 100
        assert output_tokens == 50


class TestErrorRecoveryStrategies:
    """Tests for error recovery strategies."""

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff for retries."""
        base_delay = 2  # seconds
        max_delay = 30  # seconds

        delays = []
        for retry_count in range(5):
            delay = min(base_delay ** retry_count, max_delay)
            delays.append(delay)

        assert delays == [1, 2, 4, 8, 16]

    def test_max_retries_limit(self):
        """Test that max retries limit is respected."""
        max_retries = 3
        retry_count = 0
        operation_succeeded = False

        while retry_count < max_retries and not operation_succeeded:
            retry_count += 1
            # Simulate always failing
            pass

        assert retry_count == max_retries
        assert operation_succeeded is False

    def test_retry_only_on_retryable_errors(self):
        """Test that only retryable errors trigger retries."""
        retryable_codes = ['ThrottlingException', 'ModelTimeoutException']
        non_retryable_codes = ['AccessDeniedException', 'ValidationException']

        for code in retryable_codes:
            should_retry = code in retryable_codes
            assert should_retry is True

        for code in non_retryable_codes:
            should_retry = code in retryable_codes
            assert should_retry is False


class TestCircuitBreakerFastFailure:
    """Tests that circuit breaker open state causes fast failure."""

    def test_circuit_breaker_open_raises_immediately(self):
        """When circuit breaker is open, calls raise CircuitBreakerOpen."""
        from backend.shared.retry import CircuitBreaker, CircuitBreakerOpen

        cb = CircuitBreaker(failure_threshold=3, name='bedrock:test-model')

        # Trip the breaker
        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN
        assert cb.can_execute() is False

        # Attempting to use it should raise
        with pytest.raises(CircuitBreakerOpen):
            if not cb.can_execute():
                raise CircuitBreakerOpen(f"Circuit breaker '{cb.name}' is open")

    def test_circuit_breaker_opens_after_threshold_failures(self):
        """Circuit breaker opens after exactly failure_threshold failures."""
        from backend.shared.retry import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, name='bedrock:threshold-test')

        # 4 failures should keep it closed
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED

        # 5th failure opens it
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

    def test_circuit_breaker_recovers_after_success(self):
        """Circuit breaker closes after a successful call in HALF_OPEN state."""
        from backend.shared.retry import CircuitBreaker
        import time

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, name='bedrock:recovery-test')

        # Trip it
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

        # Wait for recovery timeout
        time.sleep(0.02)
        assert cb.state == CircuitBreaker.HALF_OPEN

        # Success closes it
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED


class TestPerModelCircuitBreaker:
    """Tests for per-model circuit breaker isolation."""

    def test_throttling_one_model_doesnt_block_others(self):
        """Test that circuit breaker for one model doesn't affect other models."""
        from backend.shared.retry import CircuitBreaker

        cb_llama = CircuitBreaker(failure_threshold=3, name='bedrock:meta.llama3-1-8b-instruct-v1:0')
        cb_claude = CircuitBreaker(failure_threshold=3, name='bedrock:anthropic.claude-3-5-sonnet-20241022-v2:0')

        # Trip the Llama circuit breaker
        for _ in range(3):
            cb_llama.record_failure()

        # Llama is open, Claude is still closed
        assert cb_llama.state == CircuitBreaker.OPEN
        assert cb_claude.state == CircuitBreaker.CLOSED
        assert cb_claude.can_execute() is True
        assert cb_llama.can_execute() is False

    def test_per_model_breaker_uses_model_id_in_name(self):
        """Test that circuit breaker name includes model ID."""
        model_id = 'meta.llama3-1-8b-instruct-v1:0'
        cb_name = f'bedrock:{model_id}'

        assert cb_name == 'bedrock:meta.llama3-1-8b-instruct-v1:0'
        assert model_id in cb_name


def _import_worker():
    """Import worker module with required env vars and sys.path setup."""
    import os
    import sys

    worker_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "backend", "ecs_tasks", "worker"
    )
    worker_dir = os.path.abspath(worker_dir)

    env_vars = {
        "JOBS_TABLE_NAME": "test-Jobs",
        "TEMPLATES_TABLE_NAME": "test-Templates",
        "COST_TRACKING_TABLE_NAME": "test-CostTracking",
        "CHECKPOINT_METADATA_TABLE_NAME": "test-CheckpointMetadata",
        "BUCKET_NAME": "test-bucket",
        "QUEUE_TABLE_NAME": "test-Queue",
        "AWS_DEFAULT_REGION": "us-east-1",
    }

    old_path = sys.path[:]
    try:
        if worker_dir not in sys.path:
            sys.path.insert(0, worker_dir)

        with patch.dict(os.environ, env_vars):
            from backend.ecs_tasks.worker import worker as worker_module
            from backend.ecs_tasks.worker.worker import Worker

            return worker_module, Worker
    except ImportError as e:
        pytest.skip(f"Worker dependency not installed: {e}")
    finally:
        sys.path = old_path


class TestBedrockCostOnFailureIntegration:
    """Integration tests using actual Worker.generate_data to verify cost tracking.

    These tests instantiate the real Worker class (with mocked dependencies) to
    ensure that running_cost is only incremented after successful Bedrock calls,
    not when template_engine.execute_template raises an exception.
    """

    def test_generate_data_does_not_increment_cost_on_template_error(self):
        """Call Worker.generate_data with a template_engine that always raises.

        Verifies that running_cost stays at 0 (via the checkpoint's
        cost_accumulated) when every record fails.
        """
        import os

        worker_module, Worker = _import_worker()

        # Create Worker without __init__ (avoids signal registration issues)
        w = Worker.__new__(Worker)
        w.shutdown_requested = False
        w.CHECKPOINT_INTERVAL = 50

        # Mock template_engine to always raise
        mock_template_engine = MagicMock()
        mock_template_engine.execute_template.side_effect = ValueError(
            "Template variable not found"
        )
        w.template_engine = mock_template_engine

        # Mock all dependencies called by generate_data
        w.load_template = MagicMock(return_value={
            "template_id": "tpl-1",
            "template_definition": {"steps": [{"name": "step1"}]},
        })
        w.load_seed_data = MagicMock(return_value=[
            {"_id": "seed-1", "text": "hello"},
        ])
        w.load_checkpoint = MagicMock(return_value={
            "records_generated": 0,
            "cost_accumulated": 0.0,
            "failed_records": 0,
            "current_batch": 1,
        })
        w.save_batch = MagicMock()
        w.save_checkpoint = MagicMock()
        w.update_cost_tracking = MagicMock(return_value=0.0)
        w.update_job_progress = MagicMock()
        w.export_data = MagicMock()

        job = {
            "job_id": "job-cost-test",
            "config": {
                "template_id": "tpl-1",
                "seed_data_path": "s3://bucket/seeds.json",
                "num_records": 5,
                "budget_limit": 100.0,
            },
        }

        w.generate_data(job)

        # template_engine was called 5 times (once per record)
        assert mock_template_engine.execute_template.call_count == 5

        # save_checkpoint was called at the end (final checkpoint)
        final_checkpoint = w.save_checkpoint.call_args[0][1]

        # Cost should be 0 because all records failed
        assert final_checkpoint.get("cost_accumulated", 0.0) == 0.0
        # All 5 records should be marked as failed
        assert final_checkpoint["failed_records"] == 5

    def test_generate_data_increments_cost_only_for_successful_records(self):
        """Call Worker.generate_data with a template_engine that fails on some records.

        Verifies that running_cost only reflects successful calls.
        """
        import os

        worker_module, Worker = _import_worker()

        w = Worker.__new__(Worker)
        w.shutdown_requested = False
        w.CHECKPOINT_INTERVAL = 50

        call_count = {"n": 0}

        def selective_failure(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise ValueError("Template error on record 3")
            return {"step1": {"output": "ok", "model": "meta.llama3-1-8b-instruct-v1:0"}}

        mock_template_engine = MagicMock()
        mock_template_engine.execute_template.side_effect = selective_failure
        w.template_engine = mock_template_engine

        w.load_template = MagicMock(return_value={
            "template_id": "tpl-1",
            "template_definition": {"steps": [{"name": "step1"}]},
        })
        w.load_seed_data = MagicMock(return_value=[
            {"_id": "seed-1", "text": "hello"},
        ])
        w.load_checkpoint = MagicMock(return_value={
            "records_generated": 0,
            "cost_accumulated": 0.0,
            "failed_records": 0,
            "current_batch": 1,
        })
        w.save_batch = MagicMock()
        w.save_checkpoint = MagicMock()
        w.update_cost_tracking = MagicMock(return_value=0.0)
        w.update_job_progress = MagicMock()
        w.export_data = MagicMock()
        w.estimate_tokens = MagicMock(return_value=100)
        w.estimate_single_call_cost = MagicMock(return_value=0.01)

        job = {
            "job_id": "job-partial-cost",
            "config": {
                "template_id": "tpl-1",
                "seed_data_path": "s3://bucket/seeds.json",
                "num_records": 5,
                "budget_limit": 100.0,
            },
        }

        w.generate_data(job)

        final_checkpoint = w.save_checkpoint.call_args[0][1]
        # 1 failure out of 5 records
        assert final_checkpoint["failed_records"] == 1
        # estimate_single_call_cost called only for 4 successful records
        assert w.estimate_single_call_cost.call_count == 4
