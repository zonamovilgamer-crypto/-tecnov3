import asyncio
import os
from core.logging_config import get_logger, log_execution, setup_logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure logging is set up (it's called automatically when core.logging_config is imported,
# but explicitly calling it here for clarity in this example)
setup_logging()

# Get a logger instance for this example
example_logger = get_logger('root')

@log_execution(logger_name='root')
def example_sync_function(param1: str, param2: int) -> str:
    """
    An example synchronous function to demonstrate logging.
    """
    example_logger.info(f"Inside example_sync_function with param1={param1}, param2={param2}")
    if param2 > 5:
        raise ValueError("param2 cannot be greater than 5")
    return f"Processed: {param1} and {param2}"

@log_execution(logger_name='root')
async def example_async_function(data: dict) -> dict:
    """
    An example asynchronous function to demonstrate logging.
    """
    example_logger.debug(f"Inside example_async_function with data={data}")
    await asyncio.sleep(0.1) # Simulate async operation
    if "error" in data:
        raise RuntimeError("Simulated async error")
    data["processed"] = True
    return data

@log_execution(logger_name='scraper')
def another_component_function(item_id: str, context: dict = {}) -> str:
    """
    A function demonstrating logging for a specific component (e.g., scraper).
    """
    scraper_logger = get_logger('scraper')
    scraper_logger.info(f"Processing item {item_id}", extra={'context_data': context})
    return f"Item {item_id} processed by scraper."

async def main():
    example_logger.info("Starting logging example script.")

    # Test synchronous function
    try:
        result = example_sync_function("test_sync", 3)
        example_logger.info(f"Sync function result: {result}")
    except Exception as e:
        example_logger.error(f"Sync function failed: {e}")

    try:
        example_sync_function("test_sync_error", 10)
    except Exception as e:
        example_logger.error(f"Sync function expected error caught: {e}")

    # Test asynchronous function
    try:
        async_result = await example_async_function({"value": 123})
        example_logger.info(f"Async function result: {async_result}")
    except Exception as e:
        example_logger.error(f"Async function failed: {e}")

    try:
        await example_async_function({"value": 456, "error": True})
    except Exception as e:
        example_logger.error(f"Async function expected error caught: {e}")

    # Test component-specific logging
    another_component_function("item_001", context={"user_id": "abc", "session_id": "xyz"})
    another_component_function("item_002")

    example_logger.info("Logging example script finished.")

if __name__ == "__main__":
    asyncio.run(main())
