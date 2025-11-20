"""Cache utility functions and decorators for Redis-based caching.

This module provides production-ready caching utilities with:
- Automatic cache key generation from function arguments
- JSON serialization/deserialization for cached values
- TTL-based cache expiration
- Cache hit/miss tracking and statistics
- Decorator for automatic function result caching
- Pattern-based cache invalidation
- Comprehensive error handling and logging
"""

import functools
import hashlib
import json
from typing import Any, Callable, Optional, ParamSpec, TypeVar

from redis.exceptions import RedisError

from app.cache.redis_client import get_redis
from app.core.logging import get_logger

# Module-level logger for cache operations
logger = get_logger(__name__)

# Cache key prefix for namespacing
CACHE_PREFIX = "hft:"

# Type variables for generic decorator
P = ParamSpec("P")
R = TypeVar("R")

# Cache statistics tracking
_cache_stats = {"hits": 0, "misses": 0}


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate deterministic cache key from function arguments.

    Creates a unique cache key by hashing the string representation
    of all positional and keyword arguments. Uses SHA-256 for
    collision resistance.

    Args:
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        Hexadecimal hash string suitable for use as cache key

    Example:
        >>> key = make_cache_key("user", 123, active=True)
        >>> assert len(key) == 64  # SHA-256 produces 64 hex chars
    """
    # Sort kwargs for deterministic ordering
    sorted_kwargs = sorted(kwargs.items())

    # Create string representation of all arguments
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
    key_string = "|".join(key_parts)

    # Generate SHA-256 hash for collision resistance
    hash_object = hashlib.sha256(key_string.encode("utf-8"))
    return hash_object.hexdigest()


async def get_cached(key: str) -> Any:
    """Retrieve value from Redis cache with deserialization.

    Fetches cached value from Redis and deserializes from JSON.
    Tracks cache hit/miss statistics for monitoring.

    Args:
        key: Cache key to retrieve

    Returns:
        Deserialized cached value, or None if key doesn't exist

    Raises:
        RedisError: If Redis operation fails
        json.JSONDecodeError: If cached value is not valid JSON

    Example:
        >>> value = await get_cached("user:123")
        >>> if value is not None:
        ...     print(f"Cache hit: {value}")
    """
    try:
        redis_client = await get_redis()
        cached_value = await redis_client.get(key)

        if cached_value is None:
            _cache_stats["misses"] += 1
            logger.debug(
                "Cache miss",
                extra={
                    "cache_key": key,
                    "operation": "get",
                    "result": "miss",
                },
            )
            return None

        # Deserialize JSON value
        value = json.loads(cached_value)
        _cache_stats["hits"] += 1

        logger.debug(
            "Cache hit",
            extra={
                "cache_key": key,
                "operation": "get",
                "result": "hit",
            },
        )

        return value

    except json.JSONDecodeError as e:
        logger.error(
            "Failed to deserialize cached value",
            extra={
                "cache_key": key,
                "error": str(e),
                "cached_value": cached_value,
            },
        )
        raise

    except RedisError as e:
        logger.error(
            "Redis error during cache get",
            extra={
                "cache_key": key,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise


async def set_cached(key: str, value: Any, ttl: int = 300) -> None:
    """Store value in Redis cache with TTL.

    Serializes value to JSON and stores in Redis with specified
    time-to-live. Logs operation for observability.

    Args:
        key: Cache key to store under
        value: Value to cache (must be JSON-serializable)
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)

    Raises:
        RedisError: If Redis operation fails
        TypeError: If value is not JSON-serializable

    Example:
        >>> await set_cached("user:123", {"name": "Alice"}, ttl=600)
    """
    try:
        # Serialize value to JSON
        serialized_value = json.dumps(value, default=str)

        redis_client = await get_redis()
        await redis_client.setex(key, ttl, serialized_value)

        logger.debug(
            "Cache set",
            extra={
                "cache_key": key,
                "operation": "set",
                "ttl": ttl,
                "value_size": len(serialized_value),
            },
        )

    except TypeError as e:
        logger.error(
            "Failed to serialize value for caching",
            extra={
                "cache_key": key,
                "error": str(e),
                "value_type": type(value).__name__,
            },
        )
        raise

    except RedisError as e:
        logger.error(
            "Redis error during cache set",
            extra={
                "cache_key": key,
                "error": str(e),
                "error_type": type(e).__name__,
                "ttl": ttl,
            },
        )
        raise


async def delete_cached(key: str) -> None:
    """Delete key from Redis cache.

    Removes cached value from Redis. Safe to call even if key
    doesn't exist.

    Args:
        key: Cache key to delete

    Raises:
        RedisError: If Redis operation fails

    Example:
        >>> await delete_cached("user:123")
    """
    try:
        redis_client = await get_redis()
        deleted_count = await redis_client.delete(key)

        logger.debug(
            "Cache delete",
            extra={
                "cache_key": key,
                "operation": "delete",
                "deleted": deleted_count > 0,
            },
        )

    except RedisError as e:
        logger.error(
            "Redis error during cache delete",
            extra={
                "cache_key": key,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise


async def clear_cache_pattern(pattern: str) -> int:
    """Delete all keys matching pattern from Redis cache.

    Uses Redis SCAN for efficient pattern matching without blocking.
    Deletes all matching keys in batches.

    Args:
        pattern: Redis key pattern (supports * and ? wildcards)

    Returns:
        Number of keys deleted

    Raises:
        RedisError: If Redis operation fails

    Example:
        >>> deleted = await clear_cache_pattern("user:*")
        >>> print(f"Deleted {deleted} user cache entries")
    """
    try:
        redis_client = await get_redis()
        deleted_count = 0

        # Use SCAN for non-blocking iteration
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor, match=pattern, count=100
            )

            if keys:
                deleted_count += await redis_client.delete(*keys)

            if cursor == 0:
                break

        logger.info(
            "Cache pattern cleared",
            extra={
                "pattern": pattern,
                "operation": "clear_pattern",
                "deleted_count": deleted_count,
            },
        )

        return deleted_count

    except RedisError as e:
        logger.error(
            "Redis error during pattern clear",
            extra={
                "pattern": pattern,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise


def cached(ttl: int = 300, key_prefix: str = "") -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for automatic caching of async function results.

    Caches function return values in Redis with automatic key generation
    from function arguments. Checks cache before execution and stores
    result after successful execution.

    Args:
        ttl: Time-to-live for cached values in seconds (default: 300)
        key_prefix: Optional prefix for cache keys (default: empty)

    Returns:
        Decorator function that wraps async functions with caching

    Example:
        >>> @cached(ttl=600, key_prefix="market_data")
        ... async def get_market_data(symbol: str) -> dict:
        ...     return await fetch_from_api(symbol)
        >>>
        >>> # First call fetches from API and caches
        >>> data = await get_market_data("AAPL")
        >>> # Second call returns cached value
        >>> data = await get_market_data("AAPL")
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Generate cache key from function name and arguments
            func_name = func.__name__
            arg_hash = make_cache_key(*args, **kwargs)
            cache_key = f"{CACHE_PREFIX}{key_prefix}:{func_name}:{arg_hash}"

            try:
                # Check cache first
                cached_result = await get_cached(cache_key)
                if cached_result is not None:
                    logger.debug(
                        "Returning cached result",
                        extra={
                            "function": func_name,
                            "cache_key": cache_key,
                            "cache_hit": True,
                        },
                    )
                    return cached_result

                # Cache miss - execute function
                logger.debug(
                    "Cache miss - executing function",
                    extra={
                        "function": func_name,
                        "cache_key": cache_key,
                        "cache_hit": False,
                    },
                )

                result = await func(*args, **kwargs)

                # Store result in cache
                await set_cached(cache_key, result, ttl=ttl)

                return result

            except RedisError as e:
                # Log error but don't fail - execute function without cache
                logger.warning(
                    "Cache operation failed - executing without cache",
                    extra={
                        "function": func_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                return await func(*args, **kwargs)

        return wrapper

    return decorator


async def get_cache_stats() -> dict[str, Any]:
    """Get cache hit/miss statistics and Redis info.

    Returns comprehensive cache statistics including:
    - Hit/miss counts and rates
    - Redis memory usage
    - Connection pool statistics
    - Key count by pattern

    Returns:
        Dictionary containing cache statistics

    Example:
        >>> stats = await get_cache_stats()
        >>> print(f"Hit rate: {stats['hit_rate']:.2%}")
    """
    try:
        redis_client = await get_redis()

        # Calculate hit rate
        total_requests = _cache_stats["hits"] + _cache_stats["misses"]
        hit_rate = (
            _cache_stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

        # Get Redis info
        redis_info = await redis_client.info("memory")

        # Count keys by prefix
        cursor = 0
        key_count = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor, match=f"{CACHE_PREFIX}*", count=100
            )
            key_count += len(keys)
            if cursor == 0:
                break

        stats = {
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "key_count": key_count,
            "memory_used_bytes": redis_info.get("used_memory", 0),
            "memory_used_human": redis_info.get("used_memory_human", "0B"),
        }

        logger.info(
            "Cache statistics retrieved",
            extra={
                "operation": "get_stats",
                "hit_rate": hit_rate,
                "key_count": key_count,
            },
        )

        return stats

    except RedisError as e:
        logger.error(
            "Failed to retrieve cache statistics",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        # Return partial stats on error
        return {
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "total_requests": _cache_stats["hits"] + _cache_stats["misses"],
            "hit_rate": (
                _cache_stats["hits"] / (_cache_stats["hits"] + _cache_stats["misses"])
                if (_cache_stats["hits"] + _cache_stats["misses"]) > 0
                else 0.0
            ),
            "error": str(e),
        }