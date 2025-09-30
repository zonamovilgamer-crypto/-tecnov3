import functools
import inspect
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Callable, Dict, Generator, Optional, TypeVar, Union

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
import structlog.contextvars

from core.logging_config import get_logger

F = TypeVar("F", bound=Callable[..., Any])

class ContextLogger:
    """
    A utility class for managing structured logging context and decorators.
    """

    def __init__(self, component_name: str):
        self.logger = get_logger(component_name)

    def log_execution(self, func: F) -> F:
        """
        Decorator to log the entry and exit of a function, including arguments and return values.
        Automatically binds a trace_id if not already present.
        """
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                current_context = structlog.contextvars.get_context()
                if "trace_id" not in current_context:
                    bind_contextvars(trace_id=str(uuid.uuid4()))

                func_name = func.__name__
                module_name = func.__module__

                self.logger.info(
                    "Function entry",
                    module=module_name,
                    function=func_name,
                    args=args,
                    kwargs=kwargs,
                )

                try:
                    result = await func(*args, **kwargs)
                    self.logger.info(
                        "Function exit",
                        module=module_name,
                        function=func_name,
                        result=result,
                    )
                    return result
                except Exception as e:
                    self.logger.error(
                        "Function failed",
                        module=module_name,
                        function=func_name,
                        error=str(e),
                        exc_info=True,
                    )
                    raise
            return async_wrapper # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                current_context = structlog.contextvars.get_context()
                if "trace_id" not in current_context:
                    bind_contextvars(trace_id=str(uuid.uuid4()))

                func_name = func.__name__
                module_name = func.__module__

                self.logger.info(
                    "Function entry",
                    module=module_name,
                    function=func_name,
                    args=args,
                    kwargs=kwargs,
                )
                try:
                    result = func(*args, **kwargs)
                    self.logger.info(
                        "Function exit",
                        module=module_name,
                        function=func_name,
                        result=result,
                    )
                    return result
                except Exception as e:
                    self.logger.error(
                        "Function failed",
                        module=module_name,
                        function=func_name,
                        error=str(e),
                        exc_info=True,
                    )
                    raise
            return sync_wrapper # type: ignore

    @contextmanager
    def log_context(self, **kwargs: Any) -> Generator[None, None, None]:
        """
        Context manager to bind temporary context variables for a block of code.
        Automatically clears them on exit.
        """
        old_context = structlog.contextvars.get_context().copy()
        try:
            bind_contextvars(**kwargs)
            self.logger.debug("Context entered", context_vars=kwargs)
            yield
        finally:
            clear_contextvars()
            bind_contextvars(**old_context) # Restore previous context
            self.logger.debug("Context exited", context_vars=kwargs)

    @asynccontextmanager
    async def async_log_context(self, **kwargs: Any) -> AsyncGenerator[None, None]:
        """
        Asynchronous context manager to bind temporary context variables for a block of async code.
        Automatically clears them on exit.
        """
        old_context = structlog.contextvars.get_context().copy()
        try:
            bind_contextvars(**kwargs)
            self.logger.debug("Async context entered", context_vars=kwargs)
            yield
        finally:
            clear_contextvars()
            bind_contextvars(**old_context) # Restore previous context
            self.logger.debug("Async context exited", context_vars=kwargs)

# Example Usage (for testing purposes, can be removed later)
if __name__ == "__main__":
    scraper_context_logger = ContextLogger("scraper")

    @scraper_context_logger.log_execution
    def my_sync_function(param1: str, param2: int) -> str:
        scraper_context_logger.logger.info("Inside sync function")
        return f"Processed {param1} and {param2}"

    @scraper_context_logger.log_execution
    async def my_async_function(data: Dict[str, Any]) -> Dict[str, Any]:
        scraper_context_logger.logger.info("Inside async function", data_key=data.get("key"))
        await asyncio.sleep(0.1) # Simulate async operation
        return {"status": "done", "original_data": data}

    import asyncio

    print("--- Testing sync function ---")
    my_sync_function("test_sync", 123)

    print("\n--- Testing sync function with context ---")
    with scraper_context_logger.log_context(user_id="user-1", operation="sync_op"):
        my_sync_function("test_sync_with_context", 456)

    print("\n--- Testing async function ---")
    async def run_async_test():
        await my_async_function({"key": "value"})

    asyncio.run(run_async_test())

    print("\n--- Testing async function with context ---")
    async def run_async_context_test():
        async with scraper_context_logger.async_log_context(user_id="user-2", operation="async_op"):
            await my_async_function({"key": "another_value"})

    asyncio.run(run_async_context_test())

    print("\n--- Testing error handling ---")
    @scraper_context_logger.log_execution
    def function_that_fails():
        raise ValueError("Something went wrong!")

    try:
        function_that_fails()
    except ValueError:
        scraper_context_logger.logger.info("Caught expected error.")
