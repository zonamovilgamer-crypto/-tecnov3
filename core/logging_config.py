import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Union

import structlog
import structlog.contextvars # Import structlog.contextvars directly for get_context
from pythonjsonlogger import jsonlogger # Keep for potential future use or if needed by other parts

# --- Configuration from environment variables ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", 10 * 1024 * 1024))  # 10 MB
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", 5))

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# --- Structlog Processors ---
def add_log_level(logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Adds the log level to the event dictionary."""
    event_dict["level"] = method_name.upper()
    return event_dict

def add_async_context(logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Adds asynchronous context (e.g., trace_id, user_id) to the event dictionary."""
    context = structlog.contextvars.get_context()
    if "trace_id" in context:
        event_dict["trace_id"] = context["trace_id"]
    if "user_id" in context:
        event_dict["user_id"] = context["user_id"]
    return event_dict

# --- Shared Logging Configuration ---
def configure_shared_logging(logger_name: str, log_file_prefix: str) -> logging.Logger:
    """Configures a standard logger with file rotation and a basic formatter."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False  # Prevent logs from going to the root logger

    log_file_path = os.path.join(LOG_DIR, f"{log_file_prefix}.log")
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    # Use a basic formatter. structlog's ProcessorFormatter will override this.
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger

# --- Component-specific Standard Loggers ---
scraper_std_logger = configure_shared_logging("scraper", "scraper")
writer_std_logger = configure_shared_logging("writer", "writer")
publisher_std_logger = configure_shared_logging("publisher", "publisher")
celery_std_logger = configure_shared_logging("celery", "celery")

# Custom logger factory to return our pre-configured standard loggers
class CustomLoggerFactory(structlog.stdlib.LoggerFactory):
    def __call__(self, logger_name: str) -> logging.Logger:
        if logger_name == "scraper":
            return scraper_std_logger
        elif logger_name == "writer":
            return writer_std_logger
        elif logger_name == "publisher":
            return publisher_std_logger
        elif logger_name == "celery":
            return celery_std_logger
        else:
            return configure_shared_logging(logger_name, logger_name)

# --- Structlog Configuration ---
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars, # Merge context variables from structlog.contextvars
        add_async_context, # Custom processor to add trace_id/user_id
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter, # Crucial for structlog to format for stdlib handlers
    ],
    logger_factory=CustomLoggerFactory(), # Use our custom factory
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Returns a structlog-wrapped logger for a given component name.
    The custom logger factory handles mapping to the pre-configured standard Python loggers.
    """
    return structlog.get_logger(name)

# Example usage (for testing purposes, can be removed later)
if __name__ == "__main__":
    # Initialize context for testing
    structlog.contextvars.bind_contextvars(trace_id="test-trace-123", user_id="test-user-456")

    scraper_log = get_logger("scraper")
    writer_log = get_logger("writer")
    publisher_log = get_logger("publisher")
    celery_log = get_logger("celery")

    scraper_log.info("Scraping started", url="http://example.com")
    writer_log.warning("Content generation failed", reason="API error", article_id=1)
    publisher_log.error("Failed to publish", article_id=1, exc_info=True)
    celery_log.debug("Celery task received", task_id="abc-123")

    # Clear context
    structlog.contextvars.clear_contextvars()

    # Test without context
    scraper_log.info("Scraping finished without explicit context")
