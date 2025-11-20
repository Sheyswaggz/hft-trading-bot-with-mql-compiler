"""Health check endpoints."""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy"}


@router.get("/health/db")
async def database_health_check(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Database health check endpoint.

    Args:
        db: Database session

    Returns:
        Database health status

    Raises:
        HTTPException: If database is unhealthy
    """
    try:
        # Execute a simple query to check database connectivity
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503, detail="Database connection failed"
        ) from e