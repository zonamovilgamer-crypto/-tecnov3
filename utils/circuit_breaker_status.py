import os
import redis
import time
from typing import List # Added for List type hint
from pybreaker import CircuitBreakerState
from core.circuit_breaker import RedisStorage, get_circuit_breaker, CIRCUIT_BREAKER_ENABLED
from core.logging_config import get_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_logger('circuit_breaker_monitor')

def get_all_circuit_breaker_names() -> List[str]:
    """
    Retrieves all circuit breaker names from Redis.
    """
    if not CIRCUIT_BREAKER_ENABLED:
        return []

    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        keys = redis_client.keys("circuit_breaker:*:state")
        return [key.split(':')[1] for key in keys]
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Redis to get circuit breaker names: {e}")
        return []

def display_circuit_breaker_status():
    """
    Displays the current status of all configured circuit breakers.
    """
    if not CIRCUIT_BREAKER_ENABLED:
        logger.info("Circuit Breakers are disabled. No status to display.")
        print("\n--- Circuit Breaker Status (DISABLED) ---")
        print("Circuit breakers are currently disabled via CIRCUIT_BREAKER_ENABLED=false in .env")
        return

    print("\n--- Circuit Breaker Status ---")
    cb_names = get_all_circuit_breaker_names()
    if not cb_names:
        print("No active circuit breakers found in Redis.")
        return

    for name in cb_names:
        breaker = get_circuit_breaker(name)
        state = breaker.current_state
        fail_count = breaker.fail_counter
        reset_timeout = breaker.reset_timeout

        status_line = f"  - {name}: {state.upper()}"
        if state == CircuitBreakerState.OPEN:
            open_until = breaker.opened_until
            remaining_time = max(0, int(open_until - time.time()))
            status_line += f" (Failures: {fail_count}, Open for: {remaining_time}s remaining)"
        elif state == CircuitBreakerState.HALF_OPEN:
            status_line += f" (Failures: {fail_count}, Testing recovery)"
        else: # CLOSED
            status_line += f" (Failures: {fail_count}/{breaker.fail_max})"
        print(status_line)

def reset_circuit_breaker(name: str):
    """
    Forces a specific circuit breaker to the CLOSED state.
    """
    if not CIRCUIT_BREAKER_ENABLED:
        logger.warning(f"Circuit breakers are disabled. Cannot reset '{name}'.")
        print(f"Circuit breakers are disabled. Cannot reset '{name}'.")
        return

    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        storage = RedisStorage(redis_client)
        storage.set_closed(name)
        logger.info(f"Circuit breaker '{name}' has been forced to CLOSED state.")
        print(f"Circuit breaker '{name}' has been forced to CLOSED state.")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Redis to reset circuit breaker '{name}': {e}")
        print(f"Error: Could not connect to Redis to reset circuit breaker '{name}'.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Circuit Breaker Monitoring and Management Tool.")
    parser.add_argument("--reset", type=str, help="Name of the circuit breaker to reset to CLOSED state.")
    args = parser.parse_args()

    if args.reset:
        reset_circuit_breaker(args.reset)
    else:
        display_circuit_breaker_status()
