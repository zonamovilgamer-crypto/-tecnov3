import asyncio
import os
import time
import redis
from dotenv import load_dotenv
from core.circuit_breaker import with_circuit_breaker, CircuitBreakerOpenException, get_circuit_breaker, CIRCUIT_BREAKER_ENABLED
from core.logging_config import get_logger, setup_logging, log_execution # Added log_execution

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = get_logger('circuit_breaker_example')

# Initialize Redis client for testing
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
try:
    test_redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    test_redis_client.ping()
    logger.info("Successfully connected to Redis for circuit breaker example.")
except redis.exceptions.ConnectionError as e:
    logger.critical(f"Could not connect to Redis for circuit breaker example: {e}. Circuit breaker persistence will not work.", exc_info=True)
    test_redis_client = None

# --- Callbacks for Circuit Breaker State Changes ---
def on_open_callback(breaker_name: str):
    logger.warning(f"Callback: Circuit Breaker '{breaker_name}' is now OPEN!")
    print(f"!!! ALERT: Circuit Breaker '{breaker_name}' is now OPEN !!!")

def on_close_callback(breaker_name: str):
    logger.info(f"Callback: Circuit Breaker '{breaker_name}' is now CLOSED.")
    print(f"--- INFO: Circuit Breaker '{breaker_name}' is now CLOSED ---")

def on_half_open_callback(breaker_name: str):
    logger.info(f"Callback: Circuit Breaker '{breaker_name}' is now HALF-OPEN, testing recovery.")
    print(f"--- INFO: Circuit Breaker '{breaker_name}' is now HALF-OPEN ---")

# --- Example Service with Circuit Breaker ---
class ExternalService:
    def __init__(self, name: str):
        self.name = name
        self.fail_count = 0

    @with_circuit_breaker(
        name="external_api_service",
        failure_threshold=3,
        recovery_timeout=10, # Open for 10 seconds
        on_open=on_open_callback,
        on_close=on_close_callback,
        on_half_open=on_half_open_callback
    )
    @log_execution(logger_name='circuit_breaker_example')
    async def call_api(self, should_fail: bool = False) -> str:
        """
        Simulates an API call to an external service.
        Can be forced to fail for testing circuit breaker.
        """
        logger.info(f"Attempting to call API for {self.name}...")
        if should_fail:
            self.fail_count += 1
            logger.error(f"Simulating failure for {self.name}. Current failures: {self.fail_count}")
            raise ConnectionError(f"Simulated connection error for {self.name}")
        else:
            self.fail_count = 0 # Reset on success
            logger.info(f"API call to {self.name} successful.")
            return f"Data from {self.name}"

async def main():
    if not CIRCUIT_BREAKER_ENABLED:
        logger.warning("Circuit Breakers are disabled in .env. Example will not demonstrate breaking behavior.")
        print("\n--- Circuit Breakers are DISABLED in .env ---")
        print("Set CIRCUIT_BREAKER_ENABLED=true in your .env file to enable this example.")
        return

    service = ExternalService("TestService")
    breaker = get_circuit_breaker("external_api_service")

    print("\n--- Testing Circuit Breaker ---")

    # 1. Test CLOSED state (successful calls)
    logger.info("Phase 1: Testing CLOSED state with successful calls.")
    for _ in range(3):
        try:
            result = await service.call_api(should_fail=False)
            print(f"Success: {result}")
            await asyncio.sleep(1)
        except CircuitBreakerOpenException as e:
            print(f"Failure (expected CLOSED): {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    # 2. Force failures to open the circuit
    logger.info("Phase 2: Forcing failures to OPEN the circuit.")
    for i in range(5): # Exceeds failure_threshold=3
        try:
            result = await service.call_api(should_fail=True)
            print(f"Success (unexpected): {result}")
        except CircuitBreakerOpenException as e:
            print(f"Failure (expected OPEN): {e}")
            if i < 3: # Circuit should open after 3 failures
                logger.info("Circuit breaker should be OPEN now.")
            break # Stop trying once it's open
        except Exception as e:
            print(f"Failure (expected): {e}")
        await asyncio.sleep(0.5)

    # 3. Test OPEN state (calls should be blocked)
    logger.info(f"Phase 3: Testing OPEN state. Calls should be blocked for {breaker.reset_timeout} seconds.")
    start_open_time = time.time()
    while time.time() - start_open_time < breaker.reset_timeout + 2: # +2s buffer
        try:
            await service.call_api(should_fail=False)
            print("Success (unexpected in OPEN state)")
        except CircuitBreakerOpenException as e:
            print(f"Blocked (expected): {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        await asyncio.sleep(1)

    # 4. Test HALF-OPEN state (first call after timeout)
    logger.info("Phase 4: Testing HALF-OPEN state. First call should attempt recovery.")
    try:
        result = await service.call_api(should_fail=False) # This should be the first call in HALF-OPEN
        print(f"Success (expected HALF-OPEN recovery): {result}")
    except CircuitBreakerOpenException as e:
        print(f"Blocked (unexpected in HALF-OPEN): {e}")
    except Exception as e:
        print(f"Unexpected error during HALF-OPEN recovery: {e}")

    # 5. Continue successful calls to close the circuit
    logger.info(f"Phase 5: Continuing successful calls to CLOSE the circuit (needs {breaker.success_threshold} successes).")
    for _ in range(breaker.success_threshold + 1): # +1 to ensure it closes
        try:
            result = await service.call_api(should_fail=False)
            print(f"Success: {result}")
        except CircuitBreakerOpenException as e:
            print(f"Blocked (unexpected): {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        await asyncio.sleep(1)

    print("\n--- Circuit Breaker Test Finished ---")
    print("Final Circuit Breaker Status:")
    # Use the monitor script to display final status
    os.system(f"powershell.exe -File \"F:\\motor v2.0.1\\venv\\Scripts\\python.exe\" \"F:\\motor v2.0.1\\utils\\circuit_breaker_status.py\"")


if __name__ == "__main__":
    asyncio.run(main())
