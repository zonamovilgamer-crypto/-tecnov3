import logging
import os # Keep os for os.makedirs and VENV_SITE_PACKAGES
import sys # Re-added for sys.path workaround
from logging.handlers import RotatingFileHandler
from functools import wraps
import time
import json
import asyncio # Added for asyncio.iscoroutinefunction

# Dynamically add the venv's site-packages to sys.path
# This is a workaround for ModuleNotFoundError in some environments
VENV_SITE_PACKAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'venv', 'Lib', 'site-packages')
if VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

from pythonjsonlogger.jsonlogger import JsonFormatter
from config.motor_config import get_motor_config

config = get_motor_config()

class CustomJsonFormatter(JsonFormatter):
    """
    A custom JSON formatter to include additional fields like function name and trace_id.
    """
    def __init__(self, fmt=None, datefmt=None, style='%', *args, **kwargs):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, *args, **kwargs)
        self.default_extra_data = {}

    def add_fields(self, log_record, message, extra):
        super().add_fields(log_record, message, extra)
        if 'levelname' in log_record:
            log_record['level'] = log_record.pop('levelname')
        if 'asctime' in log_record:
            log_record['timestamp'] = log_record.pop('asctime')
        if 'funcName' in log_record:
            log_record['function'] = log_record.pop('funcName')
        if 'name' in log_record:
            log_record['logger'] = log_record.pop('name')

        # Add trace_id and context_data if available in extra or default_extra_data
        log_record['trace_id'] = extra.get('trace_id', self.default_extra_data.get('trace_id', 'N/A'))
        log_record['context_data'] = extra.get('context_data', self.default_extra_data.get('context_data', {}))

def setup_logging():
    """
    Configures structured JSON logging for the application.
    Logs are rotated and separated by component into the 'logs/' directory.
    """
    log_level_str = config.LOG_LEVEL
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_format = config.LOG_FORMAT
    log_rotation_size_mb = config.LOG_ROTATION_SIZE_MB
    log_backup_count = config.LOG_BACKUP_COUNT

    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

    # Base formatter
    if log_format == 'json':
        formatter = CustomJsonFormatter(
            fmt='%(asctime)s %(levelname)s %(name)s %(funcName)s %(message)s',
            rename_fields={'message': 'message'},
            json_ensure_ascii=False
        )
    else:
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s')

    # Define loggers for each component
    component_logs = {
        'scraper': 'scraper.log',
        'writer': 'writer.log',
        'publisher': 'publisher.log',
        'celery': 'celery.log',
        'root': 'app.log' # Default log for other modules
    }

    for component, filename in component_logs.items():
        logger = logging.getLogger(component)
        logger.setLevel(log_level)
        logger.propagate = False # Prevent logs from propagating to the root logger

        file_handler = RotatingFileHandler(
            os.path.join(log_dir, filename),
            maxBytes=log_rotation_size_mb * 1024 * 1024,
            backupCount=log_backup_count,
            encoding='utf8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Configure root logger for console output and general application logs
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add a file handler for the root logger as well
    root_file_handler = RotatingFileHandler(
        os.path.join(log_dir, component_logs['root']),
        maxBytes=log_rotation_size_mb * 1024 * 1024,
        backupCount=log_backup_count,
        encoding='utf8'
    )
    root_file_handler.setFormatter(formatter)
    root_logger.addHandler(root_file_handler)

    logging.info("Logging configured successfully.")

def get_logger(name: str):
    """
    Returns a logger instance for a given name.
    """
    return logging.getLogger(name)

def log_execution(logger_name: str = 'root'):
    """
    A decorator to log the execution of a function, including its arguments,
    return value, execution time, and any exceptions.
    Logs are structured in JSON format.
    """
    def decorator(func):
        logger = get_logger(logger_name)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_id = kwargs.get('trace_id', 'N/A')
            context_data = kwargs.get('context_data', {})

            for handler in logger.handlers:
                if isinstance(handler.formatter, CustomJsonFormatter):
                    handler.formatter.default_extra_data = {'trace_id': trace_id, 'context_data': context_data}

            logger.info(
                f"Executing async function '{func.__name__}'",
                extra={
                    'trace_id': trace_id,
                    'context_data': {
                        **context_data,
                        'args': [str(arg) for arg in args],
                        'kwargs': {k: str(v) for k, v in kwargs.items()}
                    }
                }
            )
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.info(
                    f"Async function '{func.__name__}' executed successfully in {execution_time:.4f} seconds",
                    extra={
                        'trace_id': trace_id,
                        'context_data': {
                            **context_data,
                            'execution_time_seconds': execution_time,
                            'return_value': str(result)
                        }
                    }
                )
                return result
            except Exception as e:
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.error(
                    f"Async function '{func.__name__}' failed after {execution_time:.4f} seconds with error: {e}",
                    exc_info=True,
                    extra={
                        'trace_id': trace_id,
                        'context_data': {
                            **context_data,
                            'execution_time_seconds': execution_time,
                            'error_type': type(e).__name__,
                            'error_message': str(e)
                        }
                    }
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            trace_id = kwargs.get('trace_id', 'N/A')
            context_data = kwargs.get('context_data', {})

            for handler in logger.handlers:
                if isinstance(handler.formatter, CustomJsonFormatter):
                    handler.formatter.default_extra_data = {'trace_id': trace_id, 'context_data': context_data}

            logger.info(
                f"Executing sync function '{func.__name__}'",
                extra={
                    'trace_id': trace_id,
                    'context_data': {
                        **context_data,
                        'args': [str(arg) for arg in args],
                        'kwargs': {k: str(v) for k, v in kwargs.items()}
                    }
                }
            )
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.info(
                    f"Sync function '{func.__name__}' executed successfully in {execution_time:.4f} seconds",
                    extra={
                        'trace_id': trace_id,
                        'context_data': {
                            **context_data,
                            'execution_time_seconds': execution_time,
                            'return_value': str(result)
                        }
                    }
                )
                return result
            except Exception as e:
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.error(
                    f"Sync function '{func.__name__}' failed after {execution_time:.4f} seconds with error: {e}",
                    exc_info=True,
                    extra={
                        'trace_id': trace_id,
                        'context_data': {
                            **context_data,
                            'execution_time_seconds': execution_time,
                            'error_type': type(e).__name__,
                            'error_message': str(e)
                        }
                    }
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

# Initialize logging when the module is imported
setup_logging()
