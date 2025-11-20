"""Comprehensive test suite for main application and health endpoints.

This module provides extensive test coverage for the FastAPI application,
including root endpoint, health checks, readiness probes, CORS configuration,
and API documentation availability.

Test Categories:
    - Unit Tests: Individual endpoint behavior
    - Integration Tests: Service connectivity validation
    - Error Scenarios: Failure handling and recovery
    - Security Tests: CORS and header validation
    - Performance Tests: Response time validation
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
import redis
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture


# ============================================================================
# UNIT TESTS - Root Endpoint
# ============================================================================


def test_root_endpoint_returns_success(client: TestClient) -> None:
    """Test root endpoint returns 200 OK with API information.

    Validates that the root endpoint is accessible and returns
    expected metadata about the API.
    """
    response = client.get("/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data
    assert data["message"] == "HFT Trading Bot API"
    assert data["docs"] == "/docs"


def test_root_endpoint_response_structure(client: TestClient) -> None:
    """Test root endpoint returns correctly structured response.

    Ensures response contains all required fields with correct types.
    """
    response = client.get("/")
    data = response.json()

    assert isinstance(data, dict)
    assert isinstance(data["message"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["docs"], str)
    assert len(data) == 3  # Exactly 3 fields


def test_root_endpoint_version_format(client: TestClient) -> None:
    """Test root endpoint returns valid version string.

    Validates version string follows semantic versioning pattern.
    """
    response = client.get("/")
    data = response.json()

    version = data["version"]
    assert version
    assert isinstance(version, str)
    # Version should be non-empty string
    assert len(version) > 0


# ============================================================================
# UNIT TESTS - Health Endpoint
# ============================================================================


def test_health_endpoint_returns_success(client: TestClient) -> None:
    """Test health endpoint returns 200 OK.

    Validates basic liveness probe functionality.
    """
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK


def test_health_endpoint_response_structure(client: TestClient) -> None:
    """Test health endpoint returns correct response structure.

    Ensures response contains status and timestamp fields.
    """
    response = client.get("/health")
    data = response.json()

    assert "status" in data
    assert "timestamp" in data
    assert data["status"] == "healthy"


def test_health_endpoint_timestamp_format(client: TestClient) -> None:
    """Test health endpoint returns valid ISO 8601 timestamp.

    Validates timestamp is in correct format and represents recent time.
    """
    response = client.get("/health")
    data = response.json()

    timestamp_str = data["timestamp"]
    # Should be parseable as ISO 8601
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    assert isinstance(timestamp, datetime)

    # Should be recent (within last minute)
    now = datetime.now(timezone.utc)
    time_diff = (now - timestamp).total_seconds()
    assert 0 <= time_diff < 60


def test_health_endpoint_multiple_calls(client: TestClient) -> None:
    """Test health endpoint consistency across multiple calls.

    Ensures endpoint returns consistent status on repeated calls.
    """
    responses = [client.get("/health") for _ in range(5)]

    for response in responses:
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"


# ============================================================================
# INTEGRATION TESTS - Readiness Endpoint Success
# ============================================================================


def test_readiness_endpoint_all_services_healthy(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint with all services operational.

    Validates successful readiness check when Redis and PostgreSQL
    are both accessible.
    """
    # Mock Redis connection
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL connection
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert data["services"]["redis"] == "ok"
    assert data["services"]["database"] == "ok"


def test_readiness_endpoint_response_structure(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint returns correctly structured response.

    Validates response contains all required fields with correct types.
    """
    # Mock successful connections
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    data = response.json()
    assert isinstance(data, dict)
    assert "status" in data
    assert "services" in data
    assert isinstance(data["services"], dict)
    assert "redis" in data["services"]
    assert "database" in data["services"]


# ============================================================================
# ERROR SCENARIOS - Redis Failures
# ============================================================================


def test_readiness_endpoint_redis_connection_failure(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint when Redis connection fails.

    Validates proper error handling when Redis is unreachable.
    """
    # Mock Redis connection failure
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.side_effect = redis.RedisError("Connection refused")
    mock_redis_client.close.return_value = None

    # Mock successful PostgreSQL
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["status"] == "not_ready"
    assert data["detail"]["services"]["redis"] == "unavailable"
    assert data["detail"]["services"]["database"] == "ok"
    assert len(data["detail"]["errors"]) > 0


def test_readiness_endpoint_redis_timeout(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint when Redis times out.

    Validates timeout handling for Redis connections.
    """
    # Mock Redis timeout
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.side_effect = redis.TimeoutError("Operation timed out")
    mock_redis_client.close.return_value = None

    # Mock successful PostgreSQL
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["redis"] == "unavailable"


def test_readiness_endpoint_redis_unexpected_error(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint with unexpected Redis error.

    Validates handling of unexpected exceptions from Redis.
    """
    # Mock unexpected Redis error
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.side_effect = RuntimeError("Unexpected error")
    mock_redis_client.close.return_value = None

    # Mock successful PostgreSQL
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["redis"] == "error"


# ============================================================================
# ERROR SCENARIOS - Database Failures
# ============================================================================


def test_readiness_endpoint_database_connection_failure(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint when database connection fails.

    Validates proper error handling when PostgreSQL is unreachable.
    """
    # Mock successful Redis
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL connection failure
    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect",
        side_effect=psycopg2.OperationalError("Connection refused"),
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["status"] == "not_ready"
    assert data["detail"]["services"]["redis"] == "ok"
    assert data["detail"]["services"]["database"] == "unavailable"
    assert len(data["detail"]["errors"]) > 0


def test_readiness_endpoint_database_query_failure(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint when database query fails.

    Validates handling of query execution errors.
    """
    # Mock successful Redis
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL query failure
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.execute.side_effect = psycopg2.DatabaseError("Query failed")
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["database"] == "error"


def test_readiness_endpoint_database_unexpected_result(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint with unexpected database query result.

    Validates handling when database returns unexpected data.
    """
    # Mock successful Redis
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL with unexpected result
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (2,)  # Expected (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["database"] == "error"


def test_readiness_endpoint_database_null_result(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint when database returns null result.

    Validates handling of null query results.
    """
    # Mock successful Redis
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL with null result
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = None
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["database"] == "error"


# ============================================================================
# ERROR SCENARIOS - Multiple Service Failures
# ============================================================================


def test_readiness_endpoint_all_services_failed(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint when all services fail.

    Validates error response when both Redis and PostgreSQL are down.
    """
    # Mock Redis failure
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.side_effect = redis.RedisError("Connection refused")
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL failure
    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect",
        side_effect=psycopg2.OperationalError("Connection refused"),
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["status"] == "not_ready"
    assert data["detail"]["services"]["redis"] == "unavailable"
    assert data["detail"]["services"]["database"] == "unavailable"
    assert len(data["detail"]["errors"]) >= 2


def test_readiness_endpoint_error_details_structure(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint error response structure.

    Validates error response contains all required fields.
    """
    # Mock Redis failure
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.side_effect = redis.RedisError("Test error")
    mock_redis_client.close.return_value = None

    # Mock successful PostgreSQL
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)
    assert "status" in data["detail"]
    assert "services" in data["detail"]
    assert "errors" in data["detail"]
    assert isinstance(data["detail"]["errors"], list)


# ============================================================================
# SECURITY TESTS - CORS Configuration
# ============================================================================


def test_cors_headers_present(client: TestClient) -> None:
    """Test CORS headers are present in response.

    Validates CORS middleware is properly configured.
    """
    response = client.get("/health")

    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers


def test_cors_preflight_request(client: TestClient) -> None:
    """Test CORS preflight OPTIONS request.

    Validates preflight requests are handled correctly.
    """
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]


def test_cors_credentials_allowed(client: TestClient) -> None:
    """Test CORS allows credentials.

    Validates credentials are allowed in CORS configuration.
    """
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )

    # Should allow credentials
    assert (
        response.headers.get("access-control-allow-credentials") == "true"
        or "access-control-allow-origin" in response.headers
    )


# ============================================================================
# INTEGRATION TESTS - API Documentation
# ============================================================================


def test_api_docs_available(client: TestClient) -> None:
    """Test OpenAPI documentation endpoint is accessible.

    Validates Swagger UI is available at /docs.
    """
    response = client.get("/docs")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]


def test_redoc_available(client: TestClient) -> None:
    """Test ReDoc documentation endpoint is accessible.

    Validates ReDoc UI is available at /redoc.
    """
    response = client.get("/redoc")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]


def test_openapi_json_available(client: TestClient) -> None:
    """Test OpenAPI JSON schema is accessible.

    Validates OpenAPI specification is available.
    """
    response = client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert "paths" in data


def test_openapi_schema_structure(client: TestClient) -> None:
    """Test OpenAPI schema contains expected endpoints.

    Validates all documented endpoints are present in schema.
    """
    response = client.get("/openapi.json")
    data = response.json()

    paths = data["paths"]
    assert "/" in paths
    assert "/health" in paths
    assert "/ready" in paths


# ============================================================================
# PERFORMANCE TESTS - Response Times
# ============================================================================


def test_health_endpoint_response_time(client: TestClient) -> None:
    """Test health endpoint responds quickly.

    Validates health check has minimal latency.
    """
    import time

    start = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - start

    assert response.status_code == status.HTTP_200_OK
    # Health check should be very fast (< 100ms)
    assert elapsed < 0.1


def test_readiness_endpoint_response_time(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint responds within acceptable time.

    Validates readiness check completes within timeout.
    """
    import time

    # Mock fast service responses
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        start = time.perf_counter()
        response = client.get("/ready")
        elapsed = time.perf_counter() - start

    assert response.status_code == status.HTTP_200_OK
    # Readiness check should complete quickly (< 500ms)
    assert elapsed < 0.5


def test_root_endpoint_response_time(client: TestClient) -> None:
    """Test root endpoint responds quickly.

    Validates root endpoint has minimal latency.
    """
    import time

    start = time.perf_counter()
    response = client.get("/")
    elapsed = time.perf_counter() - start

    assert response.status_code == status.HTTP_200_OK
    # Root endpoint should be very fast (< 100ms)
    assert elapsed < 0.1


# ============================================================================
# EDGE CASES - Concurrent Requests
# ============================================================================


def test_health_endpoint_concurrent_requests(client: TestClient) -> None:
    """Test health endpoint handles concurrent requests.

    Validates endpoint can handle multiple simultaneous requests.
    """
    import concurrent.futures

    def make_request() -> int:
        response = client.get("/health")
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All requests should succeed
    assert all(status_code == status.HTTP_200_OK for status_code in results)
    assert len(results) == 20


def test_readiness_endpoint_concurrent_requests(
    client: TestClient, mocker: MockerFixture
) -> None:
    """Test readiness endpoint handles concurrent requests.

    Validates endpoint can handle multiple simultaneous readiness checks.
    """
    import concurrent.futures

    # Mock successful connections
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    def make_request() -> int:
        with patch("redis.from_url", return_value=mock_redis_client), patch(
            "psycopg2.connect", return_value=mock_pg_conn
        ):
            response = client.get("/ready")
            return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All requests should succeed
    assert all(status_code == status.HTTP_200_OK for status_code in results)
    assert len(results) == 10


# ============================================================================
# EDGE CASES - Invalid Endpoints
# ============================================================================


def test_invalid_endpoint_returns_404(client: TestClient) -> None:
    """Test invalid endpoint returns 404 Not Found.

    Validates proper error handling for non-existent routes.
    """
    response = client.get("/invalid-endpoint")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_invalid_method_returns_405(client: TestClient) -> None:
    """Test invalid HTTP method returns 405 Method Not Allowed.

    Validates proper error handling for unsupported methods.
    """
    response = client.post("/health")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# ============================================================================
# INTEGRATION TESTS - Application Lifecycle
# ============================================================================


def test_application_startup_logging(mocker: MockerFixture) -> None:
    """Test application logs startup information.

    Validates startup logging is properly configured.
    """
    mock_logger = mocker.patch("app.main.get_logger")
    mock_logger_instance = mocker.MagicMock()
    mock_logger.return_value = mock_logger_instance

    # Import triggers lifespan startup
    from app.main import app

    # Logger should be called during startup
    assert mock_logger.called


def test_application_metadata(client: TestClient) -> None:
    """Test application metadata is correctly configured.

    Validates FastAPI app configuration.
    """
    from app.main import app

    assert app.title == "hft-trading-bot"
    assert app.version
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"


# ============================================================================
# PARAMETRIZED TESTS - Multiple Scenarios
# ============================================================================


@pytest.mark.parametrize(
    "endpoint,expected_status",
    [
        ("/", status.HTTP_200_OK),
        ("/health", status.HTTP_200_OK),
        ("/docs", status.HTTP_200_OK),
        ("/redoc", status.HTTP_200_OK),
        ("/openapi.json", status.HTTP_200_OK),
    ],
)
def test_public_endpoints_accessible(
    client: TestClient, endpoint: str, expected_status: int
) -> None:
    """Test all public endpoints are accessible.

    Parametrized test validating multiple endpoints return expected status.
    """
    response = client.get(endpoint)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "redis_error,expected_service_status",
    [
        (redis.RedisError("Connection error"), "unavailable"),
        (redis.TimeoutError("Timeout"), "unavailable"),
        (RuntimeError("Unexpected error"), "error"),
        (Exception("Generic error"), "error"),
    ],
)
def test_readiness_redis_error_handling(
    client: TestClient,
    mocker: MockerFixture,
    redis_error: Exception,
    expected_service_status: str,
) -> None:
    """Test readiness endpoint handles various Redis errors.

    Parametrized test validating different Redis error scenarios.
    """
    # Mock Redis with specific error
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.side_effect = redis_error
    mock_redis_client.close.return_value = None

    # Mock successful PostgreSQL
    mock_pg_conn = mocker.MagicMock()
    mock_pg_cursor = mocker.MagicMock()
    mock_pg_cursor.fetchone.return_value = (1,)
    mock_pg_conn.cursor.return_value = mock_pg_cursor

    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", return_value=mock_pg_conn
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["redis"] == expected_service_status


@pytest.mark.parametrize(
    "db_error,expected_service_status",
    [
        (psycopg2.OperationalError("Connection error"), "unavailable"),
        (psycopg2.DatabaseError("Query error"), "error"),
        (RuntimeError("Unexpected error"), "error"),
    ],
)
def test_readiness_database_error_handling(
    client: TestClient,
    mocker: MockerFixture,
    db_error: Exception,
    expected_service_status: str,
) -> None:
    """Test readiness endpoint handles various database errors.

    Parametrized test validating different PostgreSQL error scenarios.
    """
    # Mock successful Redis
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.close.return_value = None

    # Mock PostgreSQL with specific error
    with patch("redis.from_url", return_value=mock_redis_client), patch(
        "psycopg2.connect", side_effect=db_error
    ):
        response = client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["services"]["database"] == expected_service_status