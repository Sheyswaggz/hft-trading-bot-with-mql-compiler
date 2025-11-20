"""SQLAlchemy database models for trading bot.

This module defines the database models for:
- Market data (OHLCV)
- Orders
- Positions
- Trades
- Strategies
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class OrderType(str, PyEnum):
    """Order type enumeration."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, PyEnum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, PyEnum):
    """Order status enumeration."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, PyEnum):
    """Position side enumeration."""

    LONG = "long"
    SHORT = "short"


class MarketData(Base):
    """Market data model for OHLCV data."""

    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric(precision=20, scale=8), nullable=False)
    high = Column(Numeric(precision=20, scale=8), nullable=False)
    low = Column(Numeric(precision=20, scale=8), nullable=False)
    close = Column(Numeric(precision=20, scale=8), nullable=False)
    volume = Column(Numeric(precision=20, scale=8), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_market_data_symbol_timeframe", "symbol", "timeframe"),
        Index(
            "idx_market_data_symbol_timestamp",
            "symbol",
            "timestamp",
        ),
    )


class Order(Base):
    """Order model for trading orders."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    order_type = Column(Enum(OrderType), nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    price = Column(Numeric(precision=20, scale=8), nullable=True)
    stop_price = Column(Numeric(precision=20, scale=8), nullable=True)
    status = Column(Enum(OrderStatus), nullable=False, index=True)
    filled_quantity = Column(
        Numeric(precision=20, scale=8), default=Decimal("0")
    )
    average_fill_price = Column(Numeric(precision=20, scale=8), nullable=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    position = relationship("Position", back_populates="orders")
    strategy = relationship("Strategy", back_populates="orders")

    __table_args__ = (
        Index("idx_orders_symbol_status", "symbol", "status"),
        Index("idx_orders_created_at", "created_at"),
    )


class Position(Base):
    """Position model for open trading positions."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(PositionSide), nullable=False)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    entry_price = Column(Numeric(precision=20, scale=8), nullable=False)
    current_price = Column(Numeric(precision=20, scale=8), nullable=False)
    unrealized_pnl = Column(
        Numeric(precision=20, scale=8),
        default=Decimal("0"),
    )
    realized_pnl = Column(
        Numeric(precision=20, scale=8),
        default=Decimal("0"),
    )
    stop_loss = Column(Numeric(precision=20, scale=8), nullable=True)
    take_profit = Column(Numeric(precision=20, scale=8), nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    opened_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at = Column(DateTime(timezone=True), nullable=True)
    is_open = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    orders = relationship("Order", back_populates="position")
    trades = relationship("Trade", back_populates="position")
    strategy = relationship("Strategy", back_populates="positions")

    __table_args__ = (
        Index("idx_positions_symbol_is_open", "symbol", "is_open"),
        Index("idx_positions_opened_at", "opened_at"),
    )


class Trade(Base):
    """Trade model for completed trades."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(OrderSide), nullable=False)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    entry_price = Column(Numeric(precision=20, scale=8), nullable=False)
    exit_price = Column(Numeric(precision=20, scale=8), nullable=False)
    pnl = Column(Numeric(precision=20, scale=8), nullable=False)
    commission = Column(
        Numeric(precision=20, scale=8),
        default=Decimal("0"),
    )
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    position = relationship("Position", back_populates="trades")
    strategy = relationship("Strategy", back_populates="trades")

    __table_args__ = (
        Index("idx_trades_symbol_exit_time", "symbol", "exit_time"),
        Index("idx_trades_created_at", "created_at"),
    )


class Strategy(Base):
    """Strategy model for trading strategies."""

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    parameters = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    orders = relationship("Order", back_populates="strategy")
    positions = relationship("Position", back_populates="strategy")
    trades = relationship("Trade", back_populates="strategy")

    __table_args__ = (Index("idx_strategies_is_active", "is_active"),)