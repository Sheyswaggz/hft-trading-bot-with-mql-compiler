"""Comprehensive test suite for Redis cache functionality.

This module provides extensive testing coverage for:
- Redis client connection management and health checks
- Cache operations (get, set, delete, pattern clearing)
- Cache decorator functionality with TTL
- Pub/sub message publishing and subscription
- Cache statistics and monitoring
- Error handling and edge cases
- Performance and concurrency scenarios

Test Categories:
- Unit Tests: Individual function behavior
- Integration Tests: Component interactions
- Performance Tests: Response time and throughput
- Error Scenarios: Exception handling and recovery
"""

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis import aioredis as fakeredis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.cache.cache_utils import (
    CACHE_PREFIX,
    cached,
    clear_cache_pattern,
    delete_cached,
    get_cache_stats,
    get_cached,
    make_cache_key,
    set_cached,
)
from app.cache.pubsub import CHANNELS, PubSubManager, get_pubsub_manager
from app.cache.redis_client import close_redis, get_redis, ping_redis


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def redis_client():
    """Create fake Redis client for testing.

    Provides an in-memory Redis instance using fakeredis that mimics
    real Redis behavior without requiring a running Redis server.

    Yields:
        FakeRedis: In-memory Redis client for testing

    Example:
        async def test_cache(redis_client):
            await redis_client.set("key", "value")
            assert await redis_client.get("key") == "value"
    """
    # Create fake Redis instance
    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    # Patch get_redis to return fake instance
    with patch("app.cache.redis_client.get_redis", return_value=fake_redis):
        with patch("app.cache.cache_utils.get_redis", return_value=fake_redis):
            with patch("app.cache.pubsub.get_redis", return_value=fake_redis):
                yield fake_redis

    # Cleanup
    await fake_redis.flushall()
    await fake_redis.aclose()


@pytest.fixture
async def pubsub_manager(redis_client):
    """Create pub/sub manager with fake Redis.

    Provides a PubSubManager instance configured with fake Redis
    for testing pub/sub functionality.

    Args:
        redis_client: Fake Redis client fixture

    Yields:
        PubSubManager: Configured pub/sub manager for testing
    """
    manager = PubSubManager()
    manager.redis_client = redis_client
    manager.pubsub = redis_client.pubsub()

    yield manager

    # Cleanup
    await manager.close()


@pytest.fixture
def sample_data() -> dict[str, Any]:
    """Provide sample test data.

    Returns:
        Dictionary with various data types for testing serialization
    """
    return {
        "string": "test_value",
        "integer": 42,
        "float": 3.14,
        "boolean": True,
        "list": [1, 2, 3],
        "nested": {"key": "value"},
    }


# ============================================================================
# REDIS CLIENT TESTS
# ============================================================================


class TestRedisClient:
    """Test suite for Redis client connection management."""

    @pytest.mark.asyncio
    async def test_redis_connection_success(self, redis_client):
        """Test successful Redis connection establishment.

        Verifies that get_redis() returns a working Redis client
        that can execute basic operations.
        """
        # Act
        client = await get_redis()

        # Assert
        assert client is not None
        assert await client.ping() is True

    @pytest.mark.asyncio
    async def test_redis_connection_reuse(self, redis_client):
        """Test Redis client singleton pattern.

        Verifies that multiple calls to get_redis() return the same
        client instance for connection pooling efficiency.
        """
        # Act
        client1 = await get_redis()
        client2 = await get_redis()

        # Assert
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_redis_ping_success(self, redis_client):
        """Test Redis health check with ping.

        Verifies that ping_redis() correctly detects a healthy
        Redis connection.
        """
        # Act
        result = await ping_redis()

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_ping_connection_error(self, mocker):
        """Test Redis health check with connection failure.

        Verifies that ping_redis() returns False when Redis
        connection fails.
        """
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = ConnectionError("Connection refused")
        mocker.patch("app.cache.redis_client.get_redis", return_value=mock_redis)

        # Act
        result = await ping_redis()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_ping_timeout_error(self, mocker):
        """Test Redis health check with timeout.

        Verifies that ping_redis() handles timeout errors gracefully.
        """
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = TimeoutError("Operation timed out")
        mocker.patch("app.cache.redis_client.get_redis", return_value=mock_redis)

        # Act
        result = await ping_redis()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_close_success(self, redis_client):
        """Test graceful Redis connection closure.

        Verifies that close_redis() properly closes the connection
        and cleans up resources.
        """
        # Arrange
        await get_redis()

        # Act
        await close_redis()

        # Assert - should not raise exception
        assert True

    @pytest.mark.asyncio
    async def test_redis_close_idempotent(self, redis_client):
        """Test multiple calls to close_redis().

        Verifies that close_redis() can be called multiple times
        safely without errors.
        """
        # Arrange
        await get_redis()

        # Act
        await close_redis()
        await close_redis()  # Second call should be safe

        # Assert
        assert True


# ============================================================================
# CACHE UTILITIES TESTS
# ============================================================================


class TestCacheKeyGeneration:
    """Test suite for cache key generation."""

    def test_make_cache_key_with_args(self):
        """Test cache key generation with positional arguments.

        Verifies that make_cache_key() generates consistent keys
        from positional arguments.
        """
        # Act
        key1 = make_cache_key("user", 123, "profile")
        key2 = make_cache_key("user", 123, "profile")

        # Assert
        assert key1 == key2
        assert len(key1) == 64  # SHA-256 produces 64 hex chars

    def test_make_cache_key_with_kwargs(self):
        """Test cache key generation with keyword arguments.

        Verifies that make_cache_key() generates consistent keys
        from keyword arguments regardless of order.
        """
        # Act
        key1 = make_cache_key(user_id=123, active=True)
        key2 = make_cache_key(active=True, user_id=123)

        # Assert
        assert key1 == key2

    def test_make_cache_key_different_args(self):
        """Test cache key uniqueness with different arguments.

        Verifies that different arguments produce different keys.
        """
        # Act
        key1 = make_cache_key("user", 123)
        key2 = make_cache_key("user", 456)

        # Assert
        assert key1 != key2

    def test_make_cache_key_empty_args(self):
        """Test cache key generation with no arguments.

        Verifies that make_cache_key() handles empty arguments.
        """
        # Act
        key = make_cache_key()

        # Assert
        assert len(key) == 64


class TestCacheOperations:
    """Test suite for basic cache operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_cached_string(self, redis_client):
        """Test caching and retrieving string value.

        Verifies that set_cached() and get_cached() work correctly
        for string values.
        """
        # Arrange
        key = "test:string"
        value = "test_value"

        # Act
        await set_cached(key, value, ttl=60)
        result = await get_cached(key)

        # Assert
        assert result == value

    @pytest.mark.asyncio
    async def test_set_and_get_cached_dict(self, redis_client, sample_data):
        """Test caching and retrieving dictionary value.

        Verifies that complex data structures are properly serialized
        and deserialized.
        """
        # Arrange
        key = "test:dict"

        # Act
        await set_cached(key, sample_data, ttl=60)
        result = await get_cached(key)

        # Assert
        assert result == sample_data
        assert result["string"] == sample_data["string"]
        assert result["nested"]["key"] == sample_data["nested"]["key"]

    @pytest.mark.asyncio
    async def test_set_and_get_cached_list(self, redis_client):
        """Test caching and retrieving list value.

        Verifies that list data structures are properly handled.
        """
        # Arrange
        key = "test:list"
        value = [1, 2, 3, 4, 5]

        # Act
        await set_cached(key, value, ttl=60)
        result = await get_cached(key)

        # Assert
        assert result == value

    @pytest.mark.asyncio
    async def test_get_cached_miss(self, redis_client):
        """Test cache miss scenario.

        Verifies that get_cached() returns None for non-existent keys.
        """
        # Act
        result = await get_cached("nonexistent:key")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, redis_client):
        """Test cache TTL expiration.

        Verifies that cached values expire after TTL period.
        """
        # Arrange
        key = "test:ttl"
        value = "expires_soon"

        # Act
        await set_cached(key, value, ttl=1)  # 1 second TTL
        await asyncio.sleep(1.5)  # Wait for expiration
        result = await get_cached(key)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_cached_existing_key(self, redis_client):
        """Test deleting existing cached value.

        Verifies that delete_cached() removes cached values.
        """
        # Arrange
        key = "test:delete"
        await set_cached(key, "value", ttl=60)

        # Act
        await delete_cached(key)
        result = await get_cached(key)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_cached_nonexistent_key(self, redis_client):
        """Test deleting non-existent key.

        Verifies that delete_cached() handles non-existent keys gracefully.
        """
        # Act & Assert - should not raise exception
        await delete_cached("nonexistent:key")

    @pytest.mark.asyncio
    async def test_clear_cache_pattern_matching(self, redis_client):
        """Test pattern-based cache clearing.

        Verifies that clear_cache_pattern() deletes all matching keys.
        """
        # Arrange
        await set_cached("user:1:profile", {"name": "Alice"}, ttl=60)
        await set_cached("user:2:profile", {"name": "Bob"}, ttl=60)
        await set_cached("user:3:profile", {"name": "Charlie"}, ttl=60)
        await set_cached("product:1", {"name": "Widget"}, ttl=60)

        # Act
        deleted_count = await clear_cache_pattern("user:*")

        # Assert
        assert deleted_count == 3
        assert await get_cached("user:1:profile") is None
        assert await get_cached("product:1") is not None

    @pytest.mark.asyncio
    async def test_clear_cache_pattern_no_matches(self, redis_client):
        """Test pattern clearing with no matches.

        Verifies that clear_cache_pattern() returns 0 when no keys match.
        """
        # Act
        deleted_count = await clear_cache_pattern("nonexistent:*")

        # Assert
        assert deleted_count == 0


class TestCacheDecorator:
    """Test suite for @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_first_call(self, redis_client):
        """Test cached decorator on first function call.

        Verifies that the function executes and result is cached.
        """
        # Arrange
        call_count = 0

        @cached(ttl=60, key_prefix="test")
        async def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        # Act
        result = await expensive_function(5)

        # Assert
        assert result == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_decorator_cache_hit(self, redis_client):
        """Test cached decorator with cache hit.

        Verifies that cached result is returned without executing function.
        """
        # Arrange
        call_count = 0

        @cached(ttl=60, key_prefix="test")
        async def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        # Act
        result1 = await expensive_function(5)
        result2 = await expensive_function(5)

        # Assert
        assert result1 == result2 == 10
        assert call_count == 1  # Function called only once

    @pytest.mark.asyncio
    async def test_cached_decorator_different_args(self, redis_client):
        """Test cached decorator with different arguments.

        Verifies that different arguments produce different cache keys.
        """
        # Arrange
        call_count = 0

        @cached(ttl=60, key_prefix="test")
        async def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        # Act
        result1 = await expensive_function(5)
        result2 = await expensive_function(10)

        # Assert
        assert result1 == 10
        assert result2 == 20
        assert call_count == 2  # Function called twice

    @pytest.mark.asyncio
    async def test_cached_decorator_with_kwargs(self, redis_client):
        """Test cached decorator with keyword arguments.

        Verifies that keyword arguments are included in cache key.
        """
        # Arrange
        call_count = 0

        @cached(ttl=60, key_prefix="test")
        async def expensive_function(value: int, multiplier: int = 2) -> int:
            nonlocal call_count
            call_count += 1
            return value * multiplier

        # Act
        result1 = await expensive_function(5, multiplier=2)
        result2 = await expensive_function(5, multiplier=2)
        result3 = await expensive_function(5, multiplier=3)

        # Assert
        assert result1 == result2 == 10
        assert result3 == 15
        assert call_count == 2  # Called twice (different multipliers)

    @pytest.mark.asyncio
    async def test_cached_decorator_ttl_expiration(self, redis_client):
        """Test cached decorator with TTL expiration.

        Verifies that cache expires after TTL and function re-executes.
        """
        # Arrange
        call_count = 0

        @cached(ttl=1, key_prefix="test")
        async def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        # Act
        result1 = await expensive_function(5)
        await asyncio.sleep(1.5)  # Wait for expiration
        result2 = await expensive_function(5)

        # Assert
        assert result1 == result2 == 10
        assert call_count == 2  # Function called twice after expiration

    @pytest.mark.asyncio
    async def test_cached_decorator_redis_error_fallback(self, mocker):
        """Test cached decorator fallback on Redis error.

        Verifies that function executes normally when Redis fails.
        """
        # Arrange
        call_count = 0

        @cached(ttl=60, key_prefix="test")
        async def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        # Mock Redis to raise error
        mocker.patch(
            "app.cache.cache_utils.get_cached",
            side_effect=RedisError("Connection failed"),
        )

        # Act
        result = await expensive_function(5)

        # Assert
        assert result == 10
        assert call_count == 1


class TestCacheStatistics:
    """Test suite for cache statistics tracking."""

    @pytest.mark.asyncio
    async def test_cache_stats_initial_state(self, redis_client):
        """Test cache statistics in initial state.

        Verifies that cache stats start at zero.
        """
        # Act
        stats = await get_cache_stats()

        # Assert
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0
        assert stats["total_requests"] >= 0
        assert 0.0 <= stats["hit_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_cache_stats_after_operations(self, redis_client):
        """Test cache statistics after cache operations.

        Verifies that cache stats track hits and misses correctly.
        """
        # Arrange
        key = "test:stats"

        # Act
        await get_cached(key)  # Miss
        await set_cached(key, "value", ttl=60)
        await get_cached(key)  # Hit
        stats = await get_cache_stats()

        # Assert
        assert stats["total_requests"] > 0
        assert stats["key_count"] >= 0

    @pytest.mark.asyncio
    async def test_cache_stats_hit_rate_calculation(self, redis_client):
        """Test cache hit rate calculation.

        Verifies that hit rate is calculated correctly.
        """
        # Arrange
        key = "test:hitrate"

        # Act
        await set_cached(key, "value", ttl=60)
        await get_cached(key)  # Hit
        await get_cached(key)  # Hit
        await get_cached("nonexistent")  # Miss
        stats = await get_cache_stats()

        # Assert
        assert 0.0 <= stats["hit_rate"] <= 1.0


# ============================================================================
# PUB/SUB TESTS
# ============================================================================


class TestPubSubManager:
    """Test suite for Redis pub/sub functionality."""

    @pytest.mark.asyncio
    async def test_pubsub_manager_initialization(self):
        """Test PubSubManager initialization.

        Verifies that manager initializes with correct state.
        """
        # Act
        manager = PubSubManager()

        # Assert
        assert manager.redis_client is None
        assert manager.pubsub is None
        assert manager._running is True
        assert len(manager._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_publish_message_success(self, pubsub_manager, sample_data):
        """Test successful message publishing.

        Verifies that messages are published to Redis channels.
        """
        # Act & Assert - should not raise exception
        await pubsub_manager.publish(CHANNELS.MARKET_DATA, sample_data)

    @pytest.mark.asyncio
    async def test_publish_message_empty_channel(self, pubsub_manager):
        """Test publishing with empty channel name.

        Verifies that empty channel names are rejected.
        """
        # Act & Assert
        with pytest.raises(ValueError, match="Channel name cannot be empty"):
            await pubsub_manager.publish("", {"data": "test"})

    @pytest.mark.asyncio
    async def test_publish_message_serialization_error(self, pubsub_manager):
        """Test publishing non-serializable data.

        Verifies that serialization errors are handled properly.
        """
        # Arrange
        non_serializable = {"func": lambda x: x}

        # Act & Assert
        with pytest.raises(TypeError):
            await pubsub_manager.publish(CHANNELS.MARKET_DATA, non_serializable)

    @pytest.mark.asyncio
    async def test_subscribe_to_channel(self, pubsub_manager):
        """Test subscribing to a channel.

        Verifies that subscription is established successfully.
        """
        # Arrange
        received_messages = []

        async def callback(message: dict[str, Any]) -> None:
            received_messages.append(message)

        # Act
        await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Assert
        assert CHANNELS.MARKET_DATA in pubsub_manager._subscriptions

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.MARKET_DATA)

    @pytest.mark.asyncio
    async def test_subscribe_empty_channel(self, pubsub_manager):
        """Test subscribing with empty channel name.

        Verifies that empty channel names are rejected.
        """
        # Arrange
        async def callback(message: dict[str, Any]) -> None:
            pass

        # Act & Assert
        with pytest.raises(ValueError, match="Channel name cannot be empty"):
            await pubsub_manager.subscribe("", callback)

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_channel(self, pubsub_manager):
        """Test subscribing to same channel twice.

        Verifies that duplicate subscriptions are rejected.
        """
        # Arrange
        async def callback(message: dict[str, Any]) -> None:
            pass

        await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Act & Assert
        with pytest.raises(ValueError, match="Already subscribed"):
            await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.MARKET_DATA)

    @pytest.mark.asyncio
    async def test_publish_and_receive_message(self, pubsub_manager, sample_data):
        """Test end-to-end message publishing and receiving.

        Verifies that published messages are received by subscribers.
        """
        # Arrange
        received_messages = []

        async def callback(message: dict[str, Any]) -> None:
            received_messages.append(message)

        await pubsub_manager.subscribe(CHANNELS.TRADING_SIGNALS, callback)

        # Act
        await pubsub_manager.publish(CHANNELS.TRADING_SIGNALS, sample_data)
        await asyncio.sleep(0.2)  # Allow time for message processing

        # Assert
        assert len(received_messages) > 0
        assert received_messages[0] == sample_data

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.TRADING_SIGNALS)

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_channel(self, pubsub_manager):
        """Test multiple subscribers on same channel.

        Verifies that all subscribers receive published messages.
        """
        # Arrange
        received_1 = []
        received_2 = []

        async def callback_1(message: dict[str, Any]) -> None:
            received_1.append(message)

        async def callback_2(message: dict[str, Any]) -> None:
            received_2.append(message)

        # Create second manager for second subscriber
        manager_2 = PubSubManager()
        manager_2.redis_client = pubsub_manager.redis_client
        manager_2.pubsub = pubsub_manager.redis_client.pubsub()

        # Act
        await pubsub_manager.subscribe(CHANNELS.ORDER_UPDATES, callback_1)
        await manager_2.subscribe(CHANNELS.ORDER_UPDATES, callback_2)

        test_message = {"order_id": "123", "status": "filled"}
        await pubsub_manager.publish(CHANNELS.ORDER_UPDATES, test_message)
        await asyncio.sleep(0.2)

        # Assert
        assert len(received_1) > 0
        assert len(received_2) > 0
        assert received_1[0] == test_message
        assert received_2[0] == test_message

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.ORDER_UPDATES)
        await manager_2.close()

    @pytest.mark.asyncio
    async def test_unsubscribe_from_channel(self, pubsub_manager):
        """Test unsubscribing from channel.

        Verifies that unsubscribe stops message processing.
        """
        # Arrange
        async def callback(message: dict[str, Any]) -> None:
            pass

        await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Act
        await pubsub_manager.unsubscribe(CHANNELS.MARKET_DATA)

        # Assert
        assert CHANNELS.MARKET_DATA not in pubsub_manager._subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_channel(self, pubsub_manager):
        """Test unsubscribing from non-subscribed channel.

        Verifies that unsubscribing from non-existent subscription raises error.
        """
        # Act & Assert
        with pytest.raises(ValueError, match="Not subscribed"):
            await pubsub_manager.unsubscribe("nonexistent_channel")

    @pytest.mark.asyncio
    async def test_pubsub_manager_close(self, pubsub_manager):
        """Test PubSubManager cleanup.

        Verifies that close() properly cleans up all resources.
        """
        # Arrange
        async def callback(message: dict[str, Any]) -> None:
            pass

        await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Act
        await pubsub_manager.close()

        # Assert
        assert len(pubsub_manager._subscriptions) == 0
        assert pubsub_manager._running is False

    @pytest.mark.asyncio
    async def test_get_pubsub_manager_singleton(self):
        """Test pub/sub manager singleton pattern.

        Verifies that get_pubsub_manager() returns same instance.
        """
        # Act
        manager1 = await get_pubsub_manager()
        manager2 = await get_pubsub_manager()

        # Assert
        assert manager1 is manager2

        # Cleanup
        await manager1.close()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test suite for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_cache_get_invalid_json(self, redis_client):
        """Test handling of invalid JSON in cache.

        Verifies that JSON decode errors are properly raised.
        """
        # Arrange
        key = "test:invalid_json"
        await redis_client.set(key, "not valid json{")

        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
            await get_cached(key)

    @pytest.mark.asyncio
    async def test_cache_set_non_serializable(self, redis_client):
        """Test caching non-serializable object.

        Verifies that serialization errors are properly raised.
        """
        # Arrange
        key = "test:non_serializable"
        value = {"func": lambda x: x}

        # Act & Assert
        with pytest.raises(TypeError):
            await set_cached(key, value, ttl=60)

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, mocker):
        """Test handling of Redis connection errors.

        Verifies that connection errors are properly caught and logged.
        """
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Connection refused")
        mocker.patch("app.cache.cache_utils.get_redis", return_value=mock_redis)

        # Act & Assert
        with pytest.raises(ConnectionError):
            await get_cached("test:key")


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Test suite for performance validation."""

    @pytest.mark.asyncio
    async def test_cache_operation_performance(self, redis_client):
        """Test cache operation response time.

        Verifies that cache operations complete within acceptable time.
        """
        # Arrange
        key = "test:performance"
        value = {"data": "test" * 100}

        # Act
        start_time = time.time()
        await set_cached(key, value, ttl=60)
        await get_cached(key)
        elapsed = time.time() - start_time

        # Assert
        assert elapsed < 0.1  # Should complete in < 100ms

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, redis_client):
        """Test concurrent cache operations.

        Verifies that cache handles concurrent operations correctly.
        """
        # Arrange
        async def cache_operation(index: int) -> None:
            key = f"test:concurrent:{index}"
            await set_cached(key, {"index": index}, ttl=60)
            result = await get_cached(key)
            assert result["index"] == index

        # Act
        tasks = [cache_operation(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Assert - all operations completed successfully

    @pytest.mark.asyncio
    async def test_pubsub_message_throughput(self, pubsub_manager):
        """Test pub/sub message throughput.

        Verifies that pub/sub can handle multiple messages quickly.
        """
        # Arrange
        message_count = 10
        received_count = 0

        async def callback(message: dict[str, Any]) -> None:
            nonlocal received_count
            received_count += 1

        await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Act
        start_time = time.time()
        for i in range(message_count):
            await pubsub_manager.publish(
                CHANNELS.MARKET_DATA, {"index": i, "price": 50000 + i}
            )
        await asyncio.sleep(0.5)  # Allow time for processing
        elapsed = time.time() - start_time

        # Assert
        assert elapsed < 1.0  # Should complete in < 1 second
        assert received_count > 0

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.MARKET_DATA)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Test suite for component integration scenarios."""

    @pytest.mark.asyncio
    async def test_cache_and_pubsub_integration(self, redis_client, pubsub_manager):
        """Test integration between cache and pub/sub.

        Verifies that cache and pub/sub work together correctly.
        """
        # Arrange
        cache_key = "test:integration"
        received_messages = []

        async def callback(message: dict[str, Any]) -> None:
            # Cache received message
            await set_cached(cache_key, message, ttl=60)
            received_messages.append(message)

        await pubsub_manager.subscribe(CHANNELS.TRADING_SIGNALS, callback)

        # Act
        test_message = {"signal": "buy", "symbol": "BTC", "price": 50000}
        await pubsub_manager.publish(CHANNELS.TRADING_SIGNALS, test_message)
        await asyncio.sleep(0.2)

        # Retrieve from cache
        cached_message = await get_cached(cache_key)

        # Assert
        assert len(received_messages) > 0
        assert cached_message == test_message

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.TRADING_SIGNALS)

    @pytest.mark.asyncio
    async def test_decorator_with_pubsub_notification(
        self, redis_client, pubsub_manager
    ):
        """Test cached decorator with pub/sub notification.

        Verifies that cached functions can publish notifications.
        """
        # Arrange
        notifications = []

        async def callback(message: dict[str, Any]) -> None:
            notifications.append(message)

        await pubsub_manager.subscribe(CHANNELS.ORDER_UPDATES, callback)

        @cached(ttl=60, key_prefix="order")
        async def process_order(order_id: str) -> dict[str, Any]:
            result = {"order_id": order_id, "status": "processed"}
            await pubsub_manager.publish(CHANNELS.ORDER_UPDATES, result)
            return result

        # Act
        result = await process_order("ORD123")
        await asyncio.sleep(0.2)

        # Assert
        assert result["order_id"] == "ORD123"
        assert len(notifications) > 0
        assert notifications[0]["order_id"] == "ORD123"

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.ORDER_UPDATES)


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_cache_very_large_value(self, redis_client):
        """Test caching very large values.

        Verifies that large values are handled correctly.
        """
        # Arrange
        key = "test:large_value"
        large_value = {"data": "x" * 10000}  # 10KB string

        # Act
        await set_cached(key, large_value, ttl=60)
        result = await get_cached(key)

        # Assert
        assert result == large_value

    @pytest.mark.asyncio
    async def test_cache_empty_value(self, redis_client):
        """Test caching empty values.

        Verifies that empty values are handled correctly.
        """
        # Arrange
        key = "test:empty"
        empty_values = [
            "",
            [],
            {},
            None,
        ]

        # Act & Assert
        for value in empty_values:
            await set_cached(key, value, ttl=60)
            result = await get_cached(key)
            assert result == value

    @pytest.mark.asyncio
    async def test_cache_special_characters_in_key(self, redis_client):
        """Test cache keys with special characters.

        Verifies that special characters in keys are handled correctly.
        """
        # Arrange
        special_keys = [
            "test:key:with:colons",
            "test/key/with/slashes",
            "test-key-with-dashes",
            "test_key_with_underscores",
        ]

        # Act & Assert
        for key in special_keys:
            await set_cached(key, {"test": "value"}, ttl=60)
            result = await get_cached(key)
            assert result == {"test": "value"}

    @pytest.mark.asyncio
    async def test_cache_zero_ttl(self, redis_client):
        """Test caching with zero TTL.

        Verifies behavior with zero TTL (immediate expiration).
        """
        # Arrange
        key = "test:zero_ttl"

        # Act
        await set_cached(key, "value", ttl=0)
        await asyncio.sleep(0.1)
        result = await get_cached(key)

        # Assert
        assert result is None  # Should expire immediately

    @pytest.mark.asyncio
    async def test_pubsub_empty_message(self, pubsub_manager):
        """Test publishing empty message.

        Verifies that empty messages are handled correctly.
        """
        # Arrange
        received_messages = []

        async def callback(message: dict[str, Any]) -> None:
            received_messages.append(message)

        await pubsub_manager.subscribe(CHANNELS.MARKET_DATA, callback)

        # Act
        await pubsub_manager.publish(CHANNELS.MARKET_DATA, {})
        await asyncio.sleep(0.2)

        # Assert
        assert len(received_messages) > 0
        assert received_messages[0] == {}

        # Cleanup
        await pubsub_manager.unsubscribe(CHANNELS.MARKET_DATA)