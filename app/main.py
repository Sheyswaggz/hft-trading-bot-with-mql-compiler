"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import settings
from app.core.logging import setup_logging
from app.db.session import engine

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan manager."""
    logger.info("Starting up HFT Trading Bot API...")

    # Test database connection
    try:
        # Use sync context manager (engine.begin() is not async)
        with engine.begin() as conn:
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down HFT Trading Bot API...")
    # dispose() returns None, don't try to await it
    engine.dispose()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="High-Frequency Trading Bot with MQL Compiler",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])


@app.get("/", tags=["root"])
async def root() -> dict[str, Any]:
    """Root endpoint."""
    return {
        "message": "HFT Trading Bot API",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }