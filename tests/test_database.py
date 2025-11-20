"""Database tests for SQLAlchemy models and session management.

This module contains tests for:
- Database connection and session management
- Model creation and relationships
- CRUD operations
- Data integrity and constraints
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import database components
from app.db.base import Base
from app.db.models import (
    MarketData,
    Order,
    Position,
    Trade,
    Strategy,
    OrderType,
    OrderSide,
    OrderStatus,
    PositionSide,
)
from app.db.session import get_db, engine


@pytest.fixture
def test_db():
    """Create a test database with in-memory SQLite."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


def test_database_tables_created(test_db):
    """Test that all database tables are created correctly."""
    inspector = inspect(test_db.bind)
    tables = inspector.get_table_names()

    expected_tables = [
        "market_data",
        "orders",
        "positions",
        "trades",
        "strategies",
    ]
    for table in expected_tables:
        assert table in tables, f"Table {table} not found in database"


def test_market_data_creation(test_db):
    """Test creating and retrieving market data."""
    market_data = MarketData(
        symbol="EURUSD",
        timeframe="1m",
        timestamp=datetime.now(timezone.utc),
        open=Decimal("1.1000"),
        high=Decimal("1.1010"),
        low=Decimal("1.0990"),
        close=Decimal("1.1005"),
        volume=Decimal("1000000"),
    )

    test_db.add(market_data)
    test_db.commit()
    test_db.refresh(market_data)

    assert market_data.id is not None
    assert market_data.symbol == "EURUSD"
    assert market_data.close == Decimal("1.1005")


def test_order_creation(test_db):
    """Test creating and retrieving orders."""
    order = Order(
        symbol="EURUSD",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("1.1000"),
        status=OrderStatus.PENDING,
    )

    test_db.add(order)
    test_db.commit()
    test_db.refresh(order)

    assert order.id is not None
    assert order.symbol == "EURUSD"
    assert order.order_type == OrderType.MARKET
    assert order.status == OrderStatus.PENDING


def test_position_creation(test_db):
    """Test creating and retrieving positions."""
    position = Position(
        symbol="EURUSD",
        side=PositionSide.LONG,
        quantity=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1005"),
    )

    test_db.add(position)
    test_db.commit()
    test_db.refresh(position)

    assert position.id is not None
    assert position.symbol == "EURUSD"
    assert position.side == PositionSide.LONG
    assert position.unrealized_pnl == Decimal("5.0")


def test_trade_creation(test_db):
    """Test creating and retrieving trades."""
    trade = Trade(
        symbol="EURUSD",
        side=OrderSide.BUY,
        quantity=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        exit_price=Decimal("1.1010"),
        pnl=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
    )

    test_db.add(trade)
    test_db.commit()
    test_db.refresh(trade)

    assert trade.id is not None
    assert trade.symbol == "EURUSD"
    assert trade.pnl == Decimal("10.0")


def test_strategy_creation(test_db):
    """Test creating and retrieving strategies."""
    strategy = Strategy(
        name="Test Strategy",
        description="A test trading strategy",
        parameters={"param1": "value1", "param2": "value2"},
        is_active=True,
    )

    test_db.add(strategy)
    test_db.commit()
    test_db.refresh(strategy)

    assert strategy.id is not None
    assert strategy.name == "Test Strategy"
    assert strategy.is_active is True
    assert strategy.parameters["param1"] == "value1"


def test_order_position_relationship(test_db):
    """Test relationship between orders and positions."""
    position = Position(
        symbol="EURUSD",
        side=PositionSide.LONG,
        quantity=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1005"),
    )
    test_db.add(position)
    test_db.commit()

    order = Order(
        symbol="EURUSD",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("1.1000"),
        status=OrderStatus.FILLED,
        position_id=position.id,
    )
    test_db.add(order)
    test_db.commit()
    test_db.refresh(position)

    assert len(position.orders) == 1
    assert position.orders[0].id == order.id


def test_position_trade_relationship(test_db):
    """Test relationship between positions and trades."""
    position = Position(
        symbol="EURUSD",
        side=PositionSide.LONG,
        quantity=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1010"),
    )
    test_db.add(position)
    test_db.commit()

    trade = Trade(
        symbol="EURUSD",
        side=OrderSide.BUY,
        quantity=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        exit_price=Decimal("1.1010"),
        pnl=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        position_id=position.id,
    )
    test_db.add(trade)
    test_db.commit()
    test_db.refresh(position)

    assert len(position.trades) == 1
    assert position.trades[0].id == trade.id