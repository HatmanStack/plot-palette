"""
Plot Palette - Retry Decorator with Circuit Breaker

Provides resilient retry logic with exponential backoff and circuit breaker
pattern for protecting against cascading failures.
"""

import logging
import time
from functools import wraps
from threading import Lock
from typing import Callable, Optional, Set, Tuple, Type

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# Exceptions that should trigger retries
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ClientError,  # AWS SDK errors (includes throttling)
)

# AWS error codes that are retryable
RETRYABLE_ERROR_CODES: Set[str] = {
    'ThrottlingException',
    'Throttling',
    'RequestLimitExceeded',
    'ProvisionedThroughputExceededException',
    'ServiceUnavailable',
    'ServiceException',
    'InternalServerError',
    'TransientError',
    'ModelStreamErrorException',  # Bedrock specific
    'ModelTimeoutException',  # Bedrock specific
}


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and calls are rejected."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests are rejected immediately
    - HALF_OPEN: Testing if service has recovered

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        name: Optional name for logging
    """

    CLOSED = 'CLOSED'
    OPEN = 'OPEN'
    HALF_OPEN = 'HALF_OPEN'

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = 'default'
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> str:
        """Get current circuit state, checking for recovery timeout."""
        with self._lock:
            if self._state == self.OPEN:
                # Check if recovery timeout has passed
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.recovery_timeout:
                        self._state = self.HALF_OPEN
                        logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            return self._state

    def record_success(self):
        """Record a successful call, potentially closing the circuit."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                logger.info(f"Circuit breaker '{self.name}' closing after successful call")
            self._failure_count = 0
            self._state = self.CLOSED

    def record_failure(self):
        """Record a failed call, potentially opening the circuit."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == self.HALF_OPEN:
                # Failed while testing - reopen
                self._state = self.OPEN
                logger.warning(f"Circuit breaker '{self.name}' reopened after failed recovery test")
            elif self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' opened after {self._failure_count} failures"
                )

    def can_execute(self) -> bool:
        """Check if a call can be executed."""
        state = self.state  # This may transition OPEN -> HALF_OPEN
        return state in (self.CLOSED, self.HALF_OPEN)

    def reset(self):
        """Reset circuit breaker to initial state."""
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = None


# Global circuit breakers for different services
_circuit_breakers = {}
_circuit_breaker_lock = Lock()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    Args:
        name: Unique identifier for the circuit breaker
        **kwargs: Arguments passed to CircuitBreaker constructor

    Returns:
        CircuitBreaker instance
    """
    with _circuit_breaker_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
        return _circuit_breakers[name]


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if an exception should trigger a retry.

    Args:
        exception: The exception to check

    Returns:
        True if the error is retryable
    """
    if isinstance(exception, ClientError):
        error_code = exception.response.get('Error', {}).get('Code', '')
        return error_code in RETRYABLE_ERROR_CODES
    return False


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    circuit_breaker_name: Optional[str] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorator for retry with exponential backoff and optional circuit breaker.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff calculation
        circuit_breaker_name: Optional name of circuit breaker to use
        retryable_exceptions: Optional tuple of exception types to retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_retries=3, circuit_breaker_name='bedrock')
        def call_bedrock(client, prompt):
            return client.invoke_model(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cb = None
            if circuit_breaker_name:
                cb = get_circuit_breaker(circuit_breaker_name)
                if not cb.can_execute():
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{circuit_breaker_name}' is open"
                    )

            exceptions_to_catch = retryable_exceptions or RETRYABLE_EXCEPTIONS
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if cb:
                        cb.record_success()
                    return result

                except exceptions_to_catch as e:
                    last_exception = e

                    # Check if this specific error is retryable
                    if not is_retryable_error(e) and isinstance(e, ClientError):
                        # Non-retryable ClientError - fail immediately
                        if cb:
                            cb.record_failure()
                        raise

                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.1f}s delay. Error: {str(e)[:100]}"
                        )
                        time.sleep(delay)
                    else:
                        if cb:
                            cb.record_failure()
                        logger.error(
                            f"All {max_retries} retries exhausted for {func.__name__}. "
                            f"Final error: {str(e)[:200]}"
                        )

            # Re-raise the last exception if all retries failed
            if last_exception:
                raise last_exception

        return wrapper
    return decorator
