import time
import asyncio # Added for asyncio.iscoroutinefunction
from functools import wraps
from typing import Callable, Any, Dict, Optional, List
from pybreaker import CircuitBreaker as PyCircuitBreaker, CircuitBreakerError, CircuitBreakerState, CircuitBreakerStorage, CircuitBreakerListener

from core.logging_config import get_logger, log_execution
from config.motor_config import get_motor_config
from providers.cache_provider import redis # Import the global redis client

logger = get_logger('circuit_breaker')

config = get_motor_config()

class RedisStorage(CircuitBreakerStorage):
    """
    A Redis-based storage for circuit breaker state.
    """
    def __init__(self, redis_client, namespace: str = "circuit_breaker"): # Type hint changed as redis.Redis is not directly imported
        self.redis = redis_client
        self.namespace = namespace

    def _key(self, name: str) -> str:
        return f"{self.namespace}:{name}"

    def _state_key(self, name: str) -> str:
        return f"{self._key(name)}:state"

    def _fail_count_key(self, name: str) -> str:
        return f"{self._key(name)}:fail_count"

    def _open_until_key(self, name: str) -> str:
        return f"{self._key(name)}:open_until"

    def increment_failure_count(self, name: str, failure_threshold: int) -> int:
        """Increments the failure count for the given circuit breaker."""
        with self.redis.pipeline() as pipe:
            pipe.incr(self._fail_count_key(name))
            pipe.expire(self._fail_count_key(name), 3600) # Expire after 1 hour to prevent stale counts
            fail_count = pipe.execute()[0]
        return fail_count

    def reset_failure_count(self, name: str) -> None:
        """Resets the failure count for the given circuit breaker."""
        self.redis.delete(self._fail_count_key(name))

    def state(self, name: str) -> CircuitBreakerState:
        """Returns the current state of the circuit breaker."""
        state_str = self.redis.get(self._state_key(name))
        if state_str:
            return CircuitBreakerState(state_str.decode('utf-8'))
        return CircuitBreakerState.CLOSED

    def last_failure_time(self, name: str) -> Optional[float]:
        """Returns the timestamp of the last failure."""
        open_until = self.redis.get(self._open_until_key(name))
        return float(open_until.decode('utf-8')) if open_until else None

    def set_closed(self, name: str) -> None:
        """Sets the circuit breaker state to CLOSED."""
        self.redis.set(self._state_key(name), CircuitBreakerState.CLOSED.value)
        self.redis.delete(self._open_until_key(name))
        self.reset_failure_count(name)
        logger.info(f"Circuit breaker '{name}' set to CLOSED.")

    def set_open(self, name: str, timeout: int) -> None:
        """Sets the circuit breaker state to OPEN."""
        open_until = time.time() + timeout
        self.redis.set(self._state_key(name), CircuitBreakerState.OPEN.value)
        self.redis.set(self._open_until_key(name), open_until)
        self.reset_failure_count(name)
        logger.warning(f"Circuit breaker '{name}' set to OPEN until {time.ctime(open_until)}.")

    def set_half_open(self, name: str) -> None:
        """Sets the circuit breaker state to HALF_OPEN."""
        self.redis.set(self._state_key(name), CircuitBreakerState.HALF_OPEN.value)
        logger.info(f"Circuit breaker '{name}' set to HALF_OPEN.")

class CircuitBreakerLogger(CircuitBreakerListener):
    """
    A listener for circuit breaker events that logs state changes.
    """
    def __init__(self, service_name: str, on_open_cb: Optional[Callable] = None,
                 on_close_cb: Optional[Callable] = None, on_half_open_cb: Optional[Callable] = None):
        self.service_name = service_name
        self.on_open_cb = on_open_cb
        self.on_close_cb = on_close_cb
        self.on_half_open_cb = on_half_open_cb

    def state_change(self, cb_name: str, old_state: str, new_state: str):
        logger.info(f"Circuit breaker '{cb_name}' changed state from {old_state} to {new_state}",
                    service=self.service_name, old_state=old_state, new_state=new_state)
        if new_state == CircuitBreakerState.OPEN.value and self.on_open_cb:
            self.on_open_cb(cb_name)
        elif new_state == CircuitBreakerState.CLOSED.value and self.on_close_cb:
            self.on_close_cb(cb_name)
        elif new_state == CircuitBreakerState.HALF_OPEN.value and self.on_half_open_cb:
            self.on_half_open_cb(cb_name)

class CircuitBreakerOpenException(Exception):
    """Custom exception raised when a circuit breaker is open."""
    pass

# Global storage for circuit breakers
# Use the redis client from the cache_provider
circuit_breaker_storage = RedisStorage(redis) if redis else None

def get_circuit_breaker(name: str,
                       failure_threshold: Optional[int] = None,
                       recovery_timeout: Optional[int] = None,
                       expected_exception: Optional[Any] = None,
                       listeners: Optional[List[CircuitBreakerListener]] = None) -> PyCircuitBreaker:
    """
    Returns a configured CircuitBreaker instance, using Redis for persistence if available.
    """
    if not config.CIRCUIT_BREAKER_ENABLED:
        logger.info(f"Circuit Breakers are disabled. Returning a dummy breaker for '{name}'.")
        # Return a dummy object that just calls the function without breaking
        class DummyBreaker:
            def __call__(self, func):
                @wraps(func)
                def wrapper(*args, **kwargs):
                    return func(*args, **kwargs)
                return wrapper
            def __enter__(self):
                pass
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
        return DummyBreaker()

    if failure_threshold is None:
        failure_threshold = config.CIRCUIT_BREAKER_FAILURE_THRESHOLD
    if recovery_timeout is None:
        recovery_timeout = config.CIRCUIT_BREAKER_TIMEOUT_SECONDS

    if listeners is None:
        listeners = [CircuitBreakerLogger(service_name=name)]

    # Convert expected_exception to proper list format for exclude parameter
    if expected_exception is None:
        exclude_list = []
    elif isinstance(expected_exception, (list, tuple)):
        exclude_list = list(expected_exception)
    else:
        exclude_list = [expected_exception]  # Convert single class to list

    breaker = PyCircuitBreaker(
        fail_max=failure_threshold,
        reset_timeout=recovery_timeout,
        exclude=exclude_list, # Exceptions to ignore (e.g., expected business logic errors)
        listeners=listeners,
        name=name
    )
    return breaker

def with_circuit_breaker(name: str,
                         failure_threshold: Optional[int] = None,
                         recovery_timeout: Optional[int] = None,
                         expected_exception: Optional[Any] = None,
                         on_open: Optional[Callable] = None,
                         on_close: Optional[Callable] = None,
                         on_half_open: Optional[Callable] = None):
    """
    Decorator to apply a circuit breaker to a function.
    """
    def decorator(func):
        # Create a listener for this specific circuit breaker
        cb_listeners = [
            CircuitBreakerLogger(
                service_name=name,
                on_open_cb=on_open,
                on_close_cb=on_close,
                on_half_open_cb=on_half_open
            )
        ]
        breaker = get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            listeners=cb_listeners
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not config.CIRCUIT_BREAKER_ENABLED:
                return await func(*args, **kwargs)

            try:
                # Use breaker.call() instead of context manager for standard pybreaker
                return await breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.error(f"Circuit breaker '{name}' is OPEN. Skipping function '{func.__name__}'.")
                raise CircuitBreakerOpenException(f"Circuit breaker for '{name}' is OPEN.")
            except Exception as e:
                # Pybreaker automatically handles marking failures for exceptions not in 'exclude'
                logger.error(f"Function '{func.__name__}' failed, circuit breaker '{name}' recorded failure: {e}", exc_info=True)
                raise # Re-raise the original exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not config.CIRCUIT_BREAKER_ENABLED:
                return func(*args, **kwargs)

            try:
                # Use breaker.call() instead of context manager for standard pybreaker
                return breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.error(f"Circuit breaker '{name}' is OPEN. Skipping function '{func.__name__}'.")
                raise CircuitBreakerOpenException(f"Circuit breaker for '{name}' is OPEN.")
            except Exception as e:
                logger.error(f"Function '{func.__name__}' failed, circuit breaker '{name}' recorded failure: {e}", exc_info=True)
                raise

        # Determine if the function is async or sync
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
