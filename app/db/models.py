"""Database models for the HFT trading bot."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    DECIMAL,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrderType(str, PyEnum):
    """Order type enumeration."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class Side(str, PyEnum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, PyEnum):
    """Order status enumeration."""

    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class MarketData(Base):
    """Market data model for storing OHLCV and tick data."""

    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    open: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    bid: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 8), nullable=True)
    ask: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 8), nullable=True)
    spread: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Order(Base):
    """Order model for tracking trading orders."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType), nullable=False, default=OrderType.MARKET
    )
    side: Mapped[Side] = mapped_column(Enum(Side), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 8), nullable=True)
    stop_price: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(20, 8), nullable=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )
    filled_quantity: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), nullable=False, default=Decimal("0")
    )
    average_fill_price: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(20, 8), nullable=True
    )
    exchange_order_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    strategy: Mapped[Optional["Strategy"]] = relationship(
        "Strategy", back_populates="orders"
    )
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="order")


class Position(Base):
    """Position model for tracking open positions."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[Side] = mapped_column(Enum(Side), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), nullable=False, default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), nullable=False, default=Decimal("0")
    )
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    strategy: Mapped[Optional["Strategy"]] = relationship(
        "Strategy", back_populates="positions"
    )


class Trade(Base):
    """Trade model for recording executed trades."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[Side] = mapped_column(Enum(Side), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), nullable=False, default=Decimal("0")
    )
    exchange_trade_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="trades")


class Strategy(Base):
    """Strategy model for tracking trading strategies."""

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parameters: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="strategy")
    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="strategy"
    )