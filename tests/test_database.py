"""Database models and operations tests.

This module contains comprehensive tests for database models, CRUD operations,
and data integrity validation.
"""

import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import (
    MarketData,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Strategy,
    Trade,
)

# Test database URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


def test_create_market_data(db: Session) -> None:
    """Test creating market data entry."""
    market_data = MarketData(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=1000.0,
        bid=50499.0,
        ask=50501.0,
    )
    db.add(market_data)
    db.commit()
    assert market_data.id is not None


def test_create_order(db: Session) -> None:
    """Test creating an order."""
    order = Order(
        symbol="BTCUSDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.0"),
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    assert order.id is not None


def test_create_position(db: Session) -> None:
    """Test creating a position."""
    position = Position(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.0"),
        current_price=Decimal("50500.0"),
        unrealized_pnl=Decimal("50.0"),
        realized_pnl=Decimal("0.0"),
        status=OrderStatus.OPEN,
    )
    db.add(position)
    db.commit()
    assert position.id is not None


def test_create_trade(db: Session) -> None:
    """Test creating a trade."""
    # Create order first
    order = Order(
        symbol="BTCUSDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.0"),
        status=OrderStatus.FILLED,
    )
    db.add(order)
    db.commit()

    trade = Trade(
        order_id=order.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.0"),
        commission=Decimal("5.0"),
        realized_pnl=Decimal("0.0"),
    )
    db.add(trade)
    db.commit()
    assert trade.id is not None


def test_create_strategy(db: Session) -> None:
    """Test creating a strategy."""
    strategy = Strategy(
        name="Test Strategy",
        description="A test trading strategy",
        parameters={"param1": "value1"},
        is_active=True,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        total_pnl=Decimal("0.0"),
        win_rate=Decimal("0.0"),
        sharpe_ratio=Decimal("0.0"),
        max_drawdown=Decimal("0.0"),
    )
    db.add(strategy)
    db.commit()
    assert strategy.id is not None


def test_query_market_data(db: Session) -> None:
    """Test querying market data."""
    # Create test data
    market_data = MarketData(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=1000.0,
        bid=50499.0,
        ask=50501.0,
    )
    db.add(market_data)
    db.commit()

    # Query
    result = db.query(MarketData).filter_by(symbol="BTCUSDT").first()
    assert result is not None
    assert result.symbol == "BTCUSDT"


def test_query_orders(db: Session) -> None:
    """Test querying orders."""
    # Create test order
    order = Order(
        symbol="BTCUSDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.0"),
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()

    # Query
    result = db.query(Order).filter_by(symbol="BTCUSDT").first()
    assert result is not None
    assert result.status == OrderStatus.PENDING


def test_query_positions(db: Session) -> None:
    """Test querying positions."""
    # Create test position
    position = Position(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.0"),
        current_price=Decimal("50500.0"),
        unrealized_pnl=Decimal("50.0"),
        realized_pnl=Decimal("0.0"),
        status=OrderStatus.OPEN,
    )
    db.add(position)
    db.commit()

    # Query
    result = db.query(Position).filter_by(symbol="BTCUSDT").first()
    assert result is not None
    assert result.status == OrderStatus.OPEN


def test_query_trades(db: Session) -> None:
    """Test querying trades."""
    # Create order first
    order = Order(
        symbol="BTCUSDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.0"),
        status=OrderStatus.FILLED,
    )
    db.add(order)
    db.commit()

    # Create trade
    trade = Trade(
        order_id=order.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.0"),
        commission=Decimal("5.0"),
        realized_pnl=Decimal("0.0"),
    )
    db.add(trade)
    db.commit()

    # Query
    result = db.query(Trade).filter_by(symbol="BTCUSDT").first()
    assert result is not None
    assert result.order_id == order.id