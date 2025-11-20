"""Health check endpoints for liveness and readiness probes.

This module provides health monitoring endpoints for Kubernetes and load balancers
to determine application health and readiness to serve traffic.
"""

import logging
from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """Liveness probe endpoint.

    Returns basic health status indicating the application is running.
    This endpoint should always return 200 OK unless the application is crashed.

    Returns:
        dict: Health status with timestamp

    Example:
        >>> response = await health_check()
        >>> response["status"]
        'healthy'
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, str] | str]:
    """Readiness probe endpoint.

    Validates connectivity to critical dependencies (Redis and PostgreSQL).
    Returns 200 OK only when all services are accessible and operational.

    Args:
        db: Database session from dependency injection

    Returns:
        dict: Readiness status with service health details

    Raises:
        HTTPException: 503 Service Unavailable if any dependency is unreachable

    Example:
        >>> response = await readiness_check()
        >>> response["services"]["redis"]
        'ok'
    """
    settings = get_settings()
    services: dict[str, str] = {}
    errors: list[str] = []

    # Check Redis connectivity
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_client.ping()
        services["redis"] = "ok"
        logger.debug("Redis health check passed")
    except redis.RedisError as e:
        services["redis"] = "unavailable"
        error_msg = f"Redis connection failed: {e!s}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        services["redis"] = "error"
        error_msg = f"Redis health check error: {e!s}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)
    finally:
        try:
            redis_client.close()
        except Exception:
            pass

    # Check PostgreSQL connectivity
    try:
        result = await db.execute(select(1))
        row = result.scalar_one()

        if row == 1:
            services["database"] = "ok"
            logger.debug("Database health check passed")
        else:
            services["database"] = "error"
            error_msg = "Database query returned unexpected result"
            errors.append(error_msg)
            logger.error(error_msg)
    except Exception as e:
        services["database"] = "unavailable"
        error_msg = f"Database connection failed: {e!s}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)

    # Return 503 if any service is unhealthy
    if errors:
        logger.warning(
            "Readiness check failed",
            extra={"services": services, "errors": errors},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "services": services,
                "errors": errors,
            },
        )

    return {
        "status": "ready",
        "services": services,
    }