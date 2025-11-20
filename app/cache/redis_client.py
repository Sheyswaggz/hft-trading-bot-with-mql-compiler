"""Redis connection management with connection pooling.

This module provides production-ready Redis client management with:
- Connection pooling for efficient resource utilization
- Automatic reconnection with retry logic
- Health check capabilities for readiness probes
- Structured logging with operation context
- Graceful shutdown handling
"""

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.config import get_settings
from app.core.logging import get_logger

# Module-level logger for Redis operations
logger = get_logger(__name__)

# Global Redis client instance with connection pooling
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create Redis client with connection pooling.

    Returns existing client if available, otherwise creates a new client
    with optimized connection pool settings for high-frequency trading:
    - max_connections=50: Support concurrent operations
    - socket_keepalive=True: Maintain persistent connections
    - socket_connect_timeout=5: Fast failure detection
    - retry_on_timeout=True: Automatic retry for transient failures

    Returns:
        Redis: Configured async Redis client with connection pool

    Raises:
        ConnectionError: If unable to establish Redis connection
        RedisError: For other Redis-related errors

    Example:
        >>> redis_client = await get_redis()
        >>> await redis_client.set("key", "value")
        >>> value = await redis_client.get("key")
    """
    global _redis_client

    # Return existing client if already initialized
    if _redis_client is not None:
        return _redis_client

    # Get Redis URL from application settings
    settings = get_settings()

    try:
        # Create Redis client with connection pool and optimized settings
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )

        # Verify connection with ping
        await _redis_client.ping()

        logger.info(
            "Redis connection established",
            extra={
                "redis_url": settings.REDIS_URL.split("@")[-1],  # Hide credentials
                "max_connections": 50,
                "socket_keepalive": True,
                "retry_on_timeout": True,
            },
        )

        return _redis_client

    except ConnectionError as e:
        logger.error(
            "Failed to connect to Redis",
            extra={
                "error": str(e),
                "redis_url": settings.REDIS_URL.split("@")[-1],
            },
        )
        raise

    except RedisError as e:
        logger.error(
            "Redis error during initialization",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise


async def close_redis() -> None:
    """Close Redis connection and cleanup resources.

    Gracefully closes the Redis client connection pool and releases
    all associated resources. Safe to call multiple times.

    This should be called during application shutdown to ensure
    proper cleanup of connections and prevent resource leaks.

    Example:
        >>> await close_redis()
    """
    global _redis_client

    if _redis_client is not None:
        try:
            await _redis_client.aclose()
            logger.info(
                "Redis connection closed",
                extra={"status": "success"},
            )
        except RedisError as e:
            logger.error(
                "Error closing Redis connection",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        finally:
            _redis_client = None


async def ping_redis() -> bool:
    """Check Redis connectivity with ping operation.

    Performs a health check by sending a PING command to Redis.
    Used by readiness probes to verify Redis availability.

    Returns:
        bool: True if Redis is reachable and responsive, False otherwise

    Example:
        >>> is_healthy = await ping_redis()
        >>> if not is_healthy:
        ...     logger.warning("Redis is unavailable")
    """
    try:
        redis_client = await get_redis()
        await redis_client.ping()

        logger.debug(
            "Redis health check passed",
            extra={"status": "healthy"},
        )
        return True

    except ConnectionError as e:
        logger.warning(
            "Redis health check failed - connection error",
            extra={
                "error": str(e),
                "status": "unhealthy",
            },
        )
        return False

    except TimeoutError as e:
        logger.warning(
            "Redis health check failed - timeout",
            extra={
                "error": str(e),
                "status": "unhealthy",
            },
        )
        return False

    except RedisError as e:
        logger.error(
            "Redis health check failed - unexpected error",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "status": "unhealthy",
            },
        )
        return False