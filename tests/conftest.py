"""Pytest configuration and shared fixtures for testing.

This module provides reusable fixtures and configuration for the test suite,
including test client setup, mock dependencies, and async test configuration.
"""

from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.main import app


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom settings.

    Sets asyncio mode to 'auto' for automatic async test detection and execution.

    Args:
        config: Pytest configuration object
    """
    config.option.asyncio_mode = "auto"


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Create a FastAPI test client.

    Provides a test client for making HTTP requests to the FastAPI application
    without running an actual server. The client is created fresh for each test
    to ensure test isolation.

    Yields:
        TestClient: Configured test client for the FastAPI application

    Example:
        def test_health_endpoint(client):
            response = client.get("/health")
            assert response.status_code == 200
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def mock_redis(mocker: MockerFixture) -> MockerFixture:
    """Mock Redis connection for testing.

    Creates a mock Redis client that simulates Redis operations without
    requiring an actual Redis server. The mock is configured with common
    Redis methods and returns appropriate test values.

    Args:
        mocker: Pytest-mock fixture for creating mocks

    Returns:
        MockerFixture: Mocked Redis client with common methods

    Example:
        def test_cache_operation(mock_redis):
            mock_redis.get.return_value = b"cached_value"
            result = get_from_cache("key")
            assert result == "cached_value"
    """
    mock_redis_client = mocker.MagicMock()

    # Configure common Redis operations
    mock_redis_client.ping.return_value = True
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True
    mock_redis_client.delete.return_value = 1
    mock_redis_client.exists.return_value = 0
    mock_redis_client.keys.return_value = []
    mock_redis_client.flushdb.return_value = True

    # Mock async Redis methods if needed
    mock_redis_client.aclose = mocker.AsyncMock()

    return mock_redis_client


@pytest.fixture(scope="function")
def mock_db(mocker: MockerFixture) -> MockerFixture:
    """Mock database connection for testing.

    Creates a mock database session that simulates database operations without
    requiring an actual database connection. The mock is configured with common
    SQLAlchemy session methods.

    Args:
        mocker: Pytest-mock fixture for creating mocks

    Returns:
        MockerFixture: Mocked database session with common methods

    Example:
        def test_database_query(mock_db):
            mock_db.query.return_value.filter.return_value.first.return_value = user
            result = get_user_by_id(1)
            assert result == user
    """
    mock_db_session = mocker.MagicMock()

    # Configure common database operations
    mock_db_session.query.return_value = mocker.MagicMock()
    mock_db_session.add.return_value = None
    mock_db_session.commit.return_value = None
    mock_db_session.rollback.return_value = None
    mock_db_session.close.return_value = None
    mock_db_session.flush.return_value = None
    mock_db_session.refresh.return_value = None

    # Mock async database methods if needed
    mock_db_session.aclose = mocker.AsyncMock()

    # Configure query builder chain
    mock_query = mock_db_session.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.filter_by.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []
    mock_query.count.return_value = 0

    return mock_db_session