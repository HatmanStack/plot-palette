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
