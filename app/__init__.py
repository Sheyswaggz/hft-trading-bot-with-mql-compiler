"""HFT Trading Bot with MQL Compiler - Main Application Package."""

__version__ = "0.1.0"
__author__ = "HFT Trading Bot Team"

# Make key components available at package level
from app.db.base import Base
from app.db.session import get_db, engine

__all__ = ["Base", "get_db", "engine", "__version__"]