"""Redis pub/sub manager for real-time event distribution.

This module provides production-ready pub/sub infrastructure with:
- JSON message serialization for structured data
- Type-safe channel constants for event routing
- Async message publishing and subscription
- Callback-based message handling
- Graceful connection management and cleanup
- Structured logging with operation context
"""

import asyncio
import json
from typing import Any, Callable

from app.cache.redis_client import get_redis
from app.core.logging import get_logger

# Module-level logger for pub/sub operations
logger = get_logger(__name__)


# Channel constants for type-safe event routing
class CHANNELS:
    """Redis pub/sub channel names for different event types.

    Provides centralized channel name management to prevent typos
    and enable easy refactoring of channel names.
    """

    MARKET_DATA = "market_data"
    TRADING_SIGNALS = "trading_signals"
    ORDER_UPDATES = "order_updates"


# Global pub/sub manager instance
_pubsub_manager: "PubSubManager | None" = None


class PubSubManager:
    """Redis pub/sub manager for real-time event distribution.

    Manages Redis pub/sub connections with automatic message serialization,
    callback-based subscription handling, and graceful cleanup.

    Attributes:
        redis_client: Async Redis client for pub/sub operations
        pubsub: Redis pub/sub connection instance
        _subscriptions: Active subscription tasks by channel
        _running: Flag indicating if manager is active

    Example:
        >>> manager = await get_pubsub_manager()
        >>> await manager.publish(CHANNELS.MARKET_DATA, {"symbol": "BTC", "price": 50000})
        >>> async def handle_message(message: dict) -> None:
        ...     print(f"Received: {message}")
        >>> await manager.subscribe(CHANNELS.MARKET_DATA, handle_message)
    """

    def __init__(self) -> None:
        """Initialize pub/sub manager with Redis client.

        Creates Redis client and pub/sub connection instances.
        Does not establish connection until publish/subscribe is called.
        """
        self.redis_client = None
        self.pubsub = None
        self._subscriptions: dict[str, asyncio.Task[None]] = {}
        self._running = True

        logger.info(
            "PubSubManager initialized",
            extra={"status": "initialized"},
        )

    async def _ensure_connection(self) -> None:
        """Ensure Redis client and pub/sub connection are established.

        Lazily initializes Redis client and pub/sub connection on first use.
        Safe to call multiple times - only initializes once.

        Raises:
            ConnectionError: If unable to establish Redis connection
        """
        if self.redis_client is None:
            self.redis_client = await get_redis()
            self.pubsub = self.redis_client.pubsub()

            logger.debug(
                "PubSub connection established",
                extra={"status": "connected"},
            )

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish JSON message to specified channel.

        Serializes message to JSON and publishes to Redis channel.
        Subscribers on the channel will receive the message.

        Args:
            channel: Redis channel name to publish to
            message: Dictionary to serialize and publish

        Raises:
            ConnectionError: If Redis connection fails
            TypeError: If message cannot be serialized to JSON
            ValueError: If channel name is empty

        Example:
            >>> await manager.publish(
            ...     CHANNELS.TRADING_SIGNALS,
            ...     {"action": "buy", "symbol": "ETH", "quantity": 10}
            ... )
        """
        if not channel:
            raise ValueError("Channel name cannot be empty")

        await self._ensure_connection()

        try:
            # Serialize message to JSON
            json_message = json.dumps(message)

            # Publish to Redis channel
            await self.redis_client.publish(channel, json_message)

            logger.debug(
                "Message published",
                extra={
                    "channel": channel,
                    "message_size": len(json_message),
                    "message_keys": list(message.keys()),
                },
            )

        except TypeError as e:
            logger.error(
                "Failed to serialize message to JSON",
                extra={
                    "channel": channel,
                    "error": str(e),
                    "message_type": type(message).__name__,
                },
            )
            raise

        except Exception as e:
            logger.error(
                "Failed to publish message",
                extra={
                    "channel": channel,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def subscribe(
        self, channel: str, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        """Subscribe to channel and process messages with callback.

        Subscribes to Redis channel and spawns background task to process
        incoming messages. Messages are deserialized from JSON and passed
        to the callback function.

        Args:
            channel: Redis channel name to subscribe to
            callback: Async function to call for each message

        Raises:
            ConnectionError: If Redis connection fails
            ValueError: If channel name is empty or already subscribed

        Example:
            >>> async def handle_order(message: dict) -> None:
            ...     order_id = message["order_id"]
            ...     status = message["status"]
            ...     print(f"Order {order_id}: {status}")
            >>> await manager.subscribe(CHANNELS.ORDER_UPDATES, handle_order)
        """
        if not channel:
            raise ValueError("Channel name cannot be empty")

        if channel in self._subscriptions:
            raise ValueError(f"Already subscribed to channel: {channel}")

        await self._ensure_connection()

        try:
            # Subscribe to Redis channel
            await self.pubsub.subscribe(channel)

            logger.info(
                "Subscribed to channel",
                extra={"channel": channel},
            )

            # Start background task to process messages
            task = asyncio.create_task(self._process_messages(channel, callback))
            self._subscriptions[channel] = task

        except Exception as e:
            logger.error(
                "Failed to subscribe to channel",
                extra={
                    "channel": channel,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def _process_messages(
        self, channel: str, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        """Process messages from subscribed channel.

        Background task that continuously reads messages from Redis channel,
        deserializes JSON, and invokes callback function.

        Args:
            channel: Redis channel name being processed
            callback: Function to call for each message

        Note:
            This is an internal method called by subscribe().
            Runs until unsubscribe() is called or manager is closed.
        """
        logger.debug(
            "Message processing started",
            extra={"channel": channel},
        )

        try:
            while self._running:
                # Get next message from channel
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )

                if message is None:
                    # No message received, continue polling
                    await asyncio.sleep(0.1)
                    continue

                if message["type"] != "message":
                    # Skip non-message events
                    continue

                try:
                    # Deserialize JSON message
                    data = json.loads(message["data"])

                    logger.debug(
                        "Message received",
                        extra={
                            "channel": channel,
                            "message_keys": list(data.keys()),
                        },
                    )

                    # Invoke callback with deserialized data
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)

                except json.JSONDecodeError as e:
                    logger.error(
                        "Failed to deserialize message",
                        extra={
                            "channel": channel,
                            "error": str(e),
                            "raw_data": message["data"][:100],
                        },
                    )

                except Exception as e:
                    logger.error(
                        "Error processing message",
                        extra={
                            "channel": channel,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

        except asyncio.CancelledError:
            logger.info(
                "Message processing cancelled",
                extra={"channel": channel},
            )
            raise

        except Exception as e:
            logger.error(
                "Fatal error in message processing",
                extra={
                    "channel": channel,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from channel and stop message processing.

        Cancels background message processing task and unsubscribes
        from Redis channel.

        Args:
            channel: Redis channel name to unsubscribe from

        Raises:
            ValueError: If not subscribed to the channel

        Example:
            >>> await manager.unsubscribe(CHANNELS.MARKET_DATA)
        """
        if channel not in self._subscriptions:
            raise ValueError(f"Not subscribed to channel: {channel}")

        try:
            # Cancel background processing task
            task = self._subscriptions[channel]
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Remove from subscriptions
            del self._subscriptions[channel]

            # Unsubscribe from Redis channel
            if self.pubsub is not None:
                await self.pubsub.unsubscribe(channel)

            logger.info(
                "Unsubscribed from channel",
                extra={"channel": channel},
            )

        except Exception as e:
            logger.error(
                "Error unsubscribing from channel",
                extra={
                    "channel": channel,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def close(self) -> None:
        """Close pub/sub connection and cleanup resources.

        Cancels all active subscriptions, closes pub/sub connection,
        and releases resources. Safe to call multiple times.

        Example:
            >>> await manager.close()
        """
        self._running = False

        # Cancel all active subscriptions
        for channel, task in list(self._subscriptions.items()):
            try:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(
                    "Error cancelling subscription",
                    extra={
                        "channel": channel,
                        "error": str(e),
                    },
                )

        self._subscriptions.clear()

        # Close pub/sub connection
        if self.pubsub is not None:
            try:
                await self.pubsub.aclose()
                logger.info(
                    "PubSub connection closed",
                    extra={"status": "closed"},
                )
            except Exception as e:
                logger.error(
                    "Error closing pub/sub connection",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
            finally:
                self.pubsub = None

        self.redis_client = None


async def get_pubsub_manager() -> PubSubManager:
    """Get or create singleton pub/sub manager instance.

    Returns existing manager if available, otherwise creates new instance.
    Ensures only one pub/sub manager exists per application.

    Returns:
        PubSubManager: Singleton pub/sub manager instance

    Example:
        >>> manager = await get_pubsub_manager()
        >>> await manager.publish(CHANNELS.MARKET_DATA, {"price": 50000})
    """
    global _pubsub_manager

    if _pubsub_manager is None:
        _pubsub_manager = PubSubManager()

        logger.info(
            "PubSubManager singleton created",
            extra={"status": "created"},
        )

    return _pubsub_manager