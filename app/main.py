"""Main FastAPI application entry point.

This module initializes the FastAPI application with middleware, routers,
and lifecycle management for the HFT Trading Bot API.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events.

    Handles startup and shutdown tasks including logging configuration
    and resource cleanup.

    Args:
        app: FastAPI application instance

    Yields:
        None: Control to the application during its lifetime
    """
    settings = get_settings()

    # Startup: Configure logging infrastructure
    setup_logging(log_level=settings.LOG_LEVEL)
    logger = get_logger(__name__)

    logger.info(
        "Application starting",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
            "debug": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
        },
    )

    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown: Log graceful shutdown
    await close_db()
    logger.info("Database connections closed")
    logger.info(
        "Application shutting down",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
        },
    )


# Initialize FastAPI application
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="High-Frequency Trading Bot with MQL Compiler",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint providing API information.

    Returns basic information about the API including version and
    documentation links.

    Returns:
        dict: API metadata with name, version, and documentation URL
    """
    return {
        "message": "HFT Trading Bot API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )