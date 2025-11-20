"""Structured logging configuration with JSON output for production observability.

This module provides a comprehensive logging infrastructure with:
- JSON-formatted structured logs for machine parsing
- Correlation ID tracking across request boundaries
- Context-aware logging with extra fields
- Thread-safe and async-safe correlation ID management
- Production-ready configuration with sensible defaults
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variable for correlation ID tracking across async boundaries
# Thread-safe and async-safe storage for request correlation
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging output.

    Formats log records as JSON objects with standardized fields:
    - timestamp: ISO 8601 formatted UTC timestamp
    - level: Log level name (INFO, ERROR, etc.)
    - logger_name: Name of the logger that created the record
    - message: The formatted log message
    - correlation_id: Request correlation ID if set
    - Additional fields from extra parameter

    Thread-safe and handles exceptions during formatting gracefully.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format

        Returns:
            JSON-formatted string representation of the log record

        Note:
            Handles exceptions during formatting by including error details
            in the output rather than failing silently.
        """
        # Build base log structure with standard fields
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if present in context
        correlation_id = _correlation_id.get()
        if correlation_id is not None:
            log_data["correlation_id"] = correlation_id

        # Include exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from the log record
        # Filter out internal logging attributes to avoid clutter
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
            }
        }

        if extra_fields:
            log_data["extra"] = extra_fields

        # Serialize to JSON with error handling
        try:
            return json.dumps(log_data, default=str)
        except (TypeError, ValueError) as e:
            # Fallback to safe serialization if JSON encoding fails
            error_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "logger_name": "JSONFormatter",
                "message": f"Failed to serialize log record: {e!s}",
                "original_message": str(record.getMessage()),
            }
            return json.dumps(error_log)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger with JSON formatting and console output.

    Sets up the logging infrastructure for the entire application:
    - Configures root logger with specified level
    - Adds JSON formatter for structured output
    - Directs output to stdout for container compatibility
    - Removes any existing handlers to avoid duplicates

    Args:
        log_level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  Defaults to INFO for production use

    Raises:
        ValueError: If log_level is not a valid logging level name

    Example:
        >>> setup_logging("DEBUG")
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # Get root logger and clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set logging level
    root_logger.setLevel(numeric_level)

    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(JSONFormatter())

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Log configuration completion
    root_logger.info(
        "Logging configured",
        extra={"log_level": log_level, "formatter": "JSON", "output": "stdout"},
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.

    Creates or retrieves a logger that inherits configuration from root logger.
    Logger names should follow Python module naming conventions.

    Args:
        name: Name for the logger, typically __name__ of the calling module

    Returns:
        Configured logger instance ready for use

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request", extra={"user_id": 123})
    """
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for the current execution context.

    Stores the correlation ID in a context variable that is:
    - Thread-safe for concurrent requests
    - Async-safe for asyncio tasks
    - Automatically propagated to child contexts

    Args:
        correlation_id: Unique identifier for request tracing (e.g., UUID)

    Example:
        >>> set_correlation_id("550e8400-e29b-41d4-a716-446655440000")
        >>> logger.info("Request received")  # Will include correlation_id
    """
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from execution context.

    Retrieves the correlation ID set for the current context.
    Returns None if no correlation ID has been set.

    Returns:
        Current correlation ID or None if not set

    Example:
        >>> set_correlation_id("550e8400-e29b-41d4-a716-446655440000")
        >>> correlation_id = get_correlation_id()
        >>> assert correlation_id == "550e8400-e29b-41d4-a716-446655440000"
    """
    return _correlation_id.get()