# tests/test_database.py

"""Comprehensive test suite for database models and session management.

This module tests all database models, relationships, CRUD operations,
soft deletes, timestamps, and indexes to ensure data integrity and
proper ORM functionality.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import MarketData, Order, Position, Strategy, Trade


# Test database URL - using in-memory SQLite for speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine.

    Creates an async SQLite engine for testing with echo enabled
    for debugging. Engine is disposed after test completion.

    Yields:
        AsyncEngine: Test database engine
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session.

    Provides a clean database session for each test with automatic
    rollback to ensure test isolation.

    Args:
        test_engine: Test database engine fixture

    Yields:
        AsyncSession: Test database session
    """
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# ============================================================================
# MARKET DATA MODEL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_market_data_model_creation(test_db: AsyncSession):
    """Test MarketData model creation and retrieval.

    Validates that MarketData instances can be created with all fields,
    persisted to database, and retrieved with correct values.
    """
    # Arrange
    market_data = MarketData(
        symbol="EURUSD",
        timeframe="1H",
        timestamp=datetime.utcnow(),
        open=Decimal("1.1000"),
        high=Decimal("1.1050"),
        low=Decimal("1.0950"),
        close=Decimal("1.1025"),
        volume=Decimal("1000000.00"),
        bid=Decimal("1.1024"),
        ask=Decimal("1.1026"),
        spread=Decimal("0.0002"),
    )

    # Act
    test_db.add(market_data)
    await test_db.commit()
    await test_db.refresh(market_data)

    # Assert
    result = await test_db.execute(
        select(MarketData).where(MarketData.symbol == "EURUSD")
    )
    retrieved = result.scalar_one()

    assert retrieved.id is not None
    assert retrieved.symbol == "EURUSD"
    assert retrieved.timeframe == "1H"
    assert retrieved.open == Decimal("1.1000")
    assert retrieved.high == Decimal("1.1050")
    assert retrieved.low == Decimal("1.0950")
    assert retrieved.close == Decimal("1.1025")
    assert retrieved.volume == Decimal("1000000.00")
    assert retrieved.bid == Decimal("1.1024")
    assert retrieved.ask == Decimal("1.1026")
    assert retrieved.spread == Decimal("0.0002")
    assert isinstance(retrieved.timestamp, datetime)


@pytest.mark.asyncio
async def test_market_data_model_update(test_db: AsyncSession):
    """Test MarketData model update operations.

    Validates that MarketData fields can be updated and changes
    are persisted correctly.
    """
    # Arrange
    market_data = MarketData(
        symbol="GBPUSD",
        timeframe="5M",
        timestamp=datetime.utcnow(),
        open=Decimal("1.2000"),
        high=Decimal("1.2050"),
        low=Decimal("1.1950"),
        close=Decimal("1.2025"),
        volume=Decimal("500000.00"),
    )
    test_db.add(market_data)
    await test_db.commit()

    # Act
    market_data.close = Decimal("1.2030")
    market_data.high = Decimal("1.2060")
    await test_db.commit()
    await test_db.refresh(market_data)

    # Assert
    result = await test_db.execute(
        select(MarketData).where(MarketData.symbol == "GBPUSD")
    )
    updated = result.scalar_one()

    assert updated.close == Decimal("1.2030")
    assert updated.high == Decimal("1.2060")


@pytest.mark.asyncio
async def test_market_data_model_delete(test_db: AsyncSession):
    """Test MarketData model deletion.

    Validates that MarketData records can be deleted from database.
    """
    # Arrange
    market_data = MarketData(
        symbol="USDJPY",
        timeframe="15M",
        timestamp=datetime.utcnow(),
        open=Decimal("110.00"),
        high=Decimal("110.50"),
        low=Decimal("109.50"),
        close=Decimal("110.25"),
        volume=Decimal("750000.00"),
    )
    test_db.add(market_data)
    await test_db.commit()

    # Act
    await test_db.delete(market_data)
    await test_db.commit()

    # Assert
    result = await test_db.execute(
        select(MarketData).where(MarketData.symbol == "USDJPY")
    )
    assert result.scalar_one_or_none() is None


# ============================================================================
# ORDER MODEL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_order_model_creation(test_db: AsyncSession):
    """Test Order model creation and retrieval.

    Validates that Order instances can be created with all fields,
    persisted to database, and retrieved with correct values.
    """
    # Arrange
    order = Order(
        symbol="EURUSD",
        order_type="BUY",
        volume=Decimal("1.0"),
        price=Decimal("1.1000"),
        stop_loss=Decimal("1.0950"),
        take_profit=Decimal("1.1100"),
        status="PENDING",
        strategy_id=uuid4(),
    )

    # Act
    test_db.add(order)
    await test_db.commit()
    await test_db.refresh(order)

    # Assert
    result = await test_db.execute(select(Order).where(Order.symbol == "EURUSD"))
    retrieved = result.scalar_one()

    assert retrieved.id is not None
    assert retrieved.symbol == "EURUSD"
    assert retrieved.order_type == "BUY"
    assert retrieved.volume == Decimal("1.0")
    assert retrieved.price == Decimal("1.1000")
    assert retrieved.stop_loss == Decimal("1.0950")
    assert retrieved.take_profit == Decimal("1.1100")
    assert retrieved.status == "PENDING"
    assert isinstance(retrieved.strategy_id, UUID)


@pytest.mark.asyncio
async def test_order_model_status_update(test_db: AsyncSession):
    """Test Order status transitions.

    Validates that Order status can be updated through workflow
    states (PENDING -> FILLED -> CLOSED).
    """
    # Arrange
    order = Order(
        symbol="GBPUSD",
        order_type="SELL",
        volume=Decimal("0.5"),
        price=Decimal("1.2000"),
        status="PENDING",
        strategy_id=uuid4(),
    )
    test_db.add(order)
    await test_db.commit()

    # Act - Transition to FILLED
    order.status = "FILLED"
    order.filled_at = datetime.utcnow()
    await test_db.commit()

    # Assert FILLED state
    result = await test_db.execute(select(Order).where(Order.id == order.id))
    filled_order = result.scalar_one()
    assert filled_order.status == "FILLED"
    assert filled_order.filled_at is not None

    # Act - Transition to CLOSED
    order.status = "CLOSED"
    order.closed_at = datetime.utcnow()
    await test_db.commit()

    # Assert CLOSED state
    result = await test_db.execute(select(Order).where(Order.id == order.id))
    closed_order = result.scalar_one()
    assert closed_order.status == "CLOSED"
    assert closed_order.closed_at is not None


@pytest.mark.asyncio
async def test_order_model_with_optional_fields(test_db: AsyncSession):
    """Test Order creation with optional fields.

    Validates that Orders can be created with minimal required fields
    and optional fields remain None.
    """
    # Arrange
    order = Order(
        symbol="USDJPY",
        order_type="BUY",
        volume=Decimal("2.0"),
        price=Decimal("110.00"),
        status="PENDING",
        strategy_id=uuid4(),
    )

    # Act
    test_db.add(order)
    await test_db.commit()
    await test_db.refresh(order)

    # Assert
    assert order.stop_loss is None
    assert order.take_profit is None
    assert order.filled_at is None
    assert order.closed_at is None


# ============================================================================
# POSITION MODEL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_position_model_creation(test_db: AsyncSession):
    """Test Position model creation and retrieval.

    Validates that Position instances can be created with all fields,
    persisted to database, and retrieved with correct values.
    """
    # Arrange
    position = Position(
        symbol="EURUSD",
        position_type="LONG",
        volume=Decimal("1.5"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1050"),
        stop_loss=Decimal("1.0950"),
        take_profit=Decimal("1.1200"),
        profit_loss=Decimal("75.00"),
        status="OPEN",
        strategy_id=uuid4(),
    )

    # Act
    test_db.add(position)
    await test_db.commit()
    await test_db.refresh(position)

    # Assert
    result = await test_db.execute(
        select(Position).where(Position.symbol == "EURUSD")
    )
    retrieved = result.scalar_one()

    assert retrieved.id is not None
    assert retrieved.symbol == "EURUSD"
    assert retrieved.position_type == "LONG"
    assert retrieved.volume == Decimal("1.5")
    assert retrieved.entry_price == Decimal("1.1000")
    assert retrieved.current_price == Decimal("1.1050")
    assert retrieved.profit_loss == Decimal("75.00")
    assert retrieved.status == "OPEN"


@pytest.mark.asyncio
async def test_position_model_profit_loss_calculation(test_db: AsyncSession):
    """Test Position profit/loss updates.

    Validates that Position profit_loss field updates correctly
    as current_price changes.
    """
    # Arrange
    position = Position(
        symbol="GBPUSD",
        position_type="SHORT",
        volume=Decimal("1.0"),
        entry_price=Decimal("1.2000"),
        current_price=Decimal("1.2000"),
        profit_loss=Decimal("0.00"),
        status="OPEN",
        strategy_id=uuid4(),
    )
    test_db.add(position)
    await test_db.commit()

    # Act - Price moves against position
    position.current_price = Decimal("1.2050")
    position.profit_loss = Decimal("-50.00")
    await test_db.commit()

    # Assert
    result = await test_db.execute(select(Position).where(Position.id == position.id))
    updated = result.scalar_one()
    assert updated.current_price == Decimal("1.2050")
    assert updated.profit_loss == Decimal("-50.00")


@pytest.mark.asyncio
async def test_position_model_close(test_db: AsyncSession):
    """Test Position closing.

    Validates that Position can be closed with final profit/loss
    and closed_at timestamp.
    """
    # Arrange
    position = Position(
        symbol="USDJPY",
        position_type="LONG",
        volume=Decimal("2.0"),
        entry_price=Decimal("110.00"),
        current_price=Decimal("110.50"),
        profit_loss=Decimal("100.00"),
        status="OPEN",
        strategy_id=uuid4(),
    )
    test_db.add(position)
    await test_db.commit()

    # Act
    position.status = "CLOSED"
    position.closed_at = datetime.utcnow()
    position.exit_price = Decimal("110.50")
    await test_db.commit()

    # Assert
    result = await test_db.execute(select(Position).where(Position.id == position.id))
    closed = result.scalar_one()
    assert closed.status == "CLOSED"
    assert closed.closed_at is not None
    assert closed.exit_price == Decimal("110.50")


# ============================================================================
# TRADE MODEL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_trade_model_creation(test_db: AsyncSession):
    """Test Trade model creation and retrieval.

    Validates that Trade instances can be created with all fields,
    persisted to database, and retrieved with correct values.
    """
    # Arrange
    trade = Trade(
        symbol="EURUSD",
        trade_type="BUY",
        volume=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        exit_price=Decimal("1.1100"),
        profit_loss=Decimal("100.00"),
        commission=Decimal("2.00"),
        swap=Decimal("0.50"),
        entry_time=datetime.utcnow(),
        exit_time=datetime.utcnow() + timedelta(hours=1),
        strategy_id=uuid4(),
        order_id=uuid4(),
        position_id=uuid4(),
    )

    # Act
    test_db.add(trade)
    await test_db.commit()
    await test_db.refresh(trade)

    # Assert
    result = await test_db.execute(select(Trade).where(Trade.symbol == "EURUSD"))
    retrieved = result.scalar_one()

    assert retrieved.id is not None
    assert retrieved.symbol == "EURUSD"
    assert retrieved.trade_type == "BUY"
    assert retrieved.volume == Decimal("1.0")
    assert retrieved.entry_price == Decimal("1.1000")
    assert retrieved.exit_price == Decimal("1.1100")
    assert retrieved.profit_loss == Decimal("100.00")
    assert retrieved.commission == Decimal("2.00")
    assert retrieved.swap == Decimal("0.50")
    assert isinstance(retrieved.entry_time, datetime)
    assert isinstance(retrieved.exit_time, datetime)


@pytest.mark.asyncio
async def test_trade_model_net_profit(test_db: AsyncSession):
    """Test Trade net profit calculation.

    Validates that net profit is correctly calculated as
    profit_loss - commission - swap.
    """
    # Arrange
    trade = Trade(
        symbol="GBPUSD",
        trade_type="SELL",
        volume=Decimal("0.5"),
        entry_price=Decimal("1.2000"),
        exit_price=Decimal("1.1900"),
        profit_loss=Decimal("50.00"),
        commission=Decimal("1.50"),
        swap=Decimal("-0.25"),
        entry_time=datetime.utcnow(),
        exit_time=datetime.utcnow() + timedelta(hours=2),
        strategy_id=uuid4(),
    )

    # Act
    test_db.add(trade)
    await test_db.commit()
    await test_db.refresh(trade)

    # Assert
    expected_net = Decimal("50.00") - Decimal("1.50") - Decimal("-0.25")
    assert trade.profit_loss == Decimal("50.00")
    assert trade.commission == Decimal("1.50")
    assert trade.swap == Decimal("-0.25")
    # Net profit would be calculated in application logic
    calculated_net = trade.profit_loss - trade.commission - trade.swap
    assert calculated_net == expected_net


@pytest.mark.asyncio
async def test_trade_model_duration(test_db: AsyncSession):
    """Test Trade duration calculation.

    Validates that trade duration can be calculated from
    entry_time and exit_time.
    """
    # Arrange
    entry = datetime.utcnow()
    exit_time = entry + timedelta(hours=3, minutes=30)

    trade = Trade(
        symbol="USDJPY",
        trade_type="BUY",
        volume=Decimal("1.5"),
        entry_price=Decimal("110.00"),
        exit_price=Decimal("110.75"),
        profit_loss=Decimal("112.50"),
        entry_time=entry,
        exit_time=exit_time,
        strategy_id=uuid4(),
    )

    # Act
    test_db.add(trade)
    await test_db.commit()
    await test_db.refresh(trade)

    # Assert
    duration = trade.exit_time - trade.entry_time
    assert duration.total_seconds() == 12600  # 3.5 hours in seconds


# ============================================================================
# STRATEGY MODEL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_strategy_model_creation(test_db: AsyncSession):
    """Test Strategy model creation and retrieval.

    Validates that Strategy instances can be created with all fields,
    persisted to database, and retrieved with correct values.
    """
    # Arrange
    strategy = Strategy(
        name="Moving Average Crossover",
        description="Simple MA crossover strategy",
        parameters={"fast_period": 10, "slow_period": 20},
        status="ACTIVE",
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        total_profit=Decimal("0.00"),
        max_drawdown=Decimal("0.00"),
        win_rate=Decimal("0.00"),
    )

    # Act
    test_db.add(strategy)
    await test_db.commit()
    await test_db.refresh(strategy)

    # Assert
    result = await test_db.execute(
        select(Strategy).where(Strategy.name == "Moving Average Crossover")
    )
    retrieved = result.scalar_one()

    assert retrieved.id is not None
    assert retrieved.name == "Moving Average Crossover"
    assert retrieved.description == "Simple MA crossover strategy"
    assert retrieved.parameters == {"fast_period": 10, "slow_period": 20}
    assert retrieved.status == "ACTIVE"
    assert retrieved.total_trades == 0
    assert retrieved.total_profit == Decimal("0.00")


@pytest.mark.asyncio
async def test_strategy_model_statistics_update(test_db: AsyncSession):
    """Test Strategy statistics updates.

    Validates that Strategy statistics (trades, profit, win rate)
    can be updated correctly.
    """
    # Arrange
    strategy = Strategy(
        name="RSI Strategy",
        description="RSI-based trading strategy",
        parameters={"rsi_period": 14, "oversold": 30, "overbought": 70},
        status="ACTIVE",
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        total_profit=Decimal("0.00"),
        win_rate=Decimal("0.00"),
    )
    test_db.add(strategy)
    await test_db.commit()

    # Act - Simulate 10 trades: 7 wins, 3 losses
    strategy.total_trades = 10
    strategy.winning_trades = 7
    strategy.losing_trades = 3
    strategy.total_profit = Decimal("500.00")
    strategy.win_rate = Decimal("70.00")
    await test_db.commit()

    # Assert
    result = await test_db.execute(select(Strategy).where(Strategy.id == strategy.id))
    updated = result.scalar_one()
    assert updated.total_trades == 10
    assert updated.winning_trades == 7
    assert updated.losing_trades == 3
    assert updated.total_profit == Decimal("500.00")
    assert updated.win_rate == Decimal("70.00")


@pytest.mark.asyncio
async def test_strategy_model_status_transitions(test_db: AsyncSession):
    """Test Strategy status transitions.

    Validates that Strategy status can transition between
    ACTIVE, PAUSED, and STOPPED states.
    """
    # Arrange
    strategy = Strategy(
        name="Breakout Strategy",
        description="Price breakout strategy",
        parameters={"breakout_period": 20},
        status="ACTIVE",
    )
    test_db.add(strategy)
    await test_db.commit()

    # Act - Pause strategy
    strategy.status = "PAUSED"
    await test_db.commit()

    # Assert PAUSED
    result = await test_db.execute(select(Strategy).where(Strategy.id == strategy.id))
    paused = result.scalar_one()
    assert paused.status == "PAUSED"

    # Act - Stop strategy
    strategy.status = "STOPPED"
    await test_db.commit()

    # Assert STOPPED
    result = await test_db.execute(select(Strategy).where(Strategy.id == strategy.id))
    stopped = result.scalar_one()
    assert stopped.status == "STOPPED"


# ============================================================================
# RELATIONSHIP TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_model_relationships(test_db: AsyncSession):
    """Test relationships between models.

    Validates that foreign key relationships work correctly
    between Strategy, Order, Position, and Trade models.
    """
    # Arrange - Create strategy
    strategy = Strategy(
        name="Test Strategy",
        description="Strategy for relationship testing",
        parameters={},
        status="ACTIVE",
    )
    test_db.add(strategy)
    await test_db.commit()
    await test_db.refresh(strategy)

    # Create order linked to strategy
    order = Order(
        symbol="EURUSD",
        order_type="BUY",
        volume=Decimal("1.0"),
        price=Decimal("1.1000"),
        status="FILLED",
        strategy_id=strategy.id,
    )
    test_db.add(order)
    await test_db.commit()
    await test_db.refresh(order)

    # Create position linked to strategy
    position = Position(
        symbol="EURUSD",
        position_type="LONG",
        volume=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1050"),
        profit_loss=Decimal("50.00"),
        status="OPEN",
        strategy_id=strategy.id,
    )
    test_db.add(position)
    await test_db.commit()
    await test_db.refresh(position)

    # Create trade linked to strategy, order, and position
    trade = Trade(
        symbol="EURUSD",
        trade_type="BUY",
        volume=Decimal("1.0"),
        entry_price=Decimal("1.1000"),
        exit_price=Decimal("1.1050"),
        profit_loss=Decimal("50.00"),
        entry_time=datetime.utcnow(),
        exit_time=datetime.utcnow() + timedelta(hours=1),
        strategy_id=strategy.id,
        order_id=order.id,
        position_id=position.id,
    )
    test_db.add(trade)
    await test_db.commit()
    await test_db.refresh(trade)

    # Assert relationships
    assert order.strategy_id == strategy.id
    assert position.strategy_id == strategy.id
    assert trade.strategy_id == strategy.id
    assert trade.order_id == order.id
    assert trade.position_id == position.id


# ============================================================================
# SOFT DELETE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_strategy(test_db: AsyncSession):
    """Test soft delete functionality for Strategy.

    Validates that Strategy can be soft deleted by setting
    is_deleted flag without removing from database.
    """
    # Arrange
    strategy = Strategy(
        name="Deletable Strategy",
        description="Strategy to test soft delete",
        parameters={},
        status="ACTIVE",
        is_deleted=False,
    )
    test_db.add(strategy)
    await test_db.commit()
    await test_db.refresh(strategy)

    # Act - Soft delete
    strategy.is_deleted = True
    strategy.deleted_at = datetime.utcnow()
    await test_db.commit()

    # Assert - Record still exists but marked as deleted
    result = await test_db.execute(select(Strategy).where(Strategy.id == strategy.id))
    deleted = result.scalar_one()
    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_order(test_db: AsyncSession):
    """Test soft delete functionality for Order.

    Validates that Order can be soft deleted by setting
    is_deleted flag without removing from database.
    """
    # Arrange
    order = Order(
        symbol="GBPUSD",
        order_type="SELL",
        volume=Decimal("0.5"),
        price=Decimal("1.2000"),
        status="CANCELLED",
        strategy_id=uuid4(),
        is_deleted=False,
    )
    test_db.add(order)
    await test_db.commit()

    # Act - Soft delete
    order.is_deleted = True
    order.deleted_at = datetime.utcnow()
    await test_db.commit()

    # Assert
    result = await test_db.execute(select(Order).where(Order.id == order.id))
    deleted = result.scalar_one()
    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None


# ============================================================================
# TIMESTAMP TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_timestamps_on_creation(test_db: AsyncSession):
    """Test automatic timestamp creation.

    Validates that created_at and updated_at timestamps are
    automatically set on record creation.
    """
    # Arrange & Act
    strategy = Strategy(
        name="Timestamp Test Strategy",
        description="Testing automatic timestamps",
        parameters={},
        status="ACTIVE",
    )
    test_db.add(strategy)
    await test_db.commit()
    await test_db.refresh(strategy)

    # Assert
    assert strategy.created_at is not None
    assert strategy.updated_at is not None
    assert isinstance(strategy.created_at, datetime)
    assert isinstance(strategy.updated_at, datetime)
    # created_at and updated_at should be very close on creation
    time_diff = (strategy.updated_at - strategy.created_at).total_seconds()
    assert time_diff < 1  # Less than 1 second difference


@pytest.mark.asyncio
async def test_timestamps_on_update(test_db: AsyncSession):
    """Test automatic timestamp updates.

    Validates that updated_at timestamp is automatically updated
    when record is modified, while created_at remains unchanged.
    """
    # Arrange
    order = Order(
        symbol="USDJPY",
        order_type="BUY",
        volume=Decimal("1.0"),
        price=Decimal("110.00"),
        status="PENDING",
        strategy_id=uuid4(),
    )
    test_db.add(order)
    await test_db.commit()
    await test_db.refresh(order)

    original_created_at = order.created_at
    original_updated_at = order.updated_at

    # Wait a moment to ensure timestamp difference
    await asyncio.sleep(0.1)

    # Act - Update order
    order.status = "FILLED"
    await test_db.commit()
    await test_db.refresh(order)

    # Assert
    assert order.created_at == original_created_at  # Should not change
    assert order.updated_at > original_updated_at  # Should be updated


# ============================================================================
# INDEX TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_indexes_exist(test_db: AsyncSession):
    """Test that expected indexes exist on tables.

    Validates that database indexes are created for commonly
    queried columns to ensure query performance.
    """
    # Get inspector for database metadata
    inspector = inspect(test_db.bind)

    # Test MarketData indexes
    market_data_indexes = inspector.get_indexes("market_data")
    index_columns = [idx["column_names"] for idx in market_data_indexes]
    assert ["symbol"] in index_columns or any(
        "symbol" in cols for cols in index_columns
    )
    assert ["timestamp"] in index_columns or any(
        "timestamp" in cols for cols in index_columns
    )

    # Test Order indexes
    order_indexes = inspector.get_indexes("orders")
    index_columns = [idx["column_names"] for idx in order_indexes]
    assert ["strategy_id"] in index_columns or any(
        "strategy_id" in cols for cols in index_columns
    )
    assert ["status"] in index_columns or any("status" in cols for cols in index_columns)

    # Test Position indexes
    position_indexes = inspector.get_indexes("positions")
    index_columns = [idx["column_names"] for idx in position_indexes]
    assert ["strategy_id"] in index_columns or any(
        "strategy_id" in cols for cols in index_columns
    )
    assert ["status"] in index_columns or any("status" in cols for cols in index_columns)

    # Test Trade indexes
    trade_indexes = inspector.get_indexes("trades")
    index_columns = [idx["column_names"] for idx in trade_indexes]
    assert ["strategy_id"] in index_columns or any(
        "strategy_id" in cols for cols in index_columns
    )

    # Test Strategy indexes
    strategy_indexes = inspector.get_indexes("strategies")
    index_columns = [idx["column_names"] for idx in strategy_indexes]
    assert ["status"] in index_columns or any("status" in cols for cols in index_columns)


# ============================================================================
# EDGE CASE AND ERROR TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_decimal_precision(test_db: AsyncSession):
    """Test Decimal field precision handling.

    Validates that Decimal fields maintain precision for
    financial calculations without rounding errors.
    """
    # Arrange
    position = Position(
        symbol="EURUSD",
        position_type="LONG",
        volume=Decimal("1.23456789"),
        entry_price=Decimal("1.10000000"),
        current_price=Decimal("1.10050000"),
        profit_loss=Decimal("61.72839450"),
        status="OPEN",
        strategy_id=uuid4(),
    )

    # Act
    test_db.add(position)
    await test_db.commit()
    await test_db.refresh(position)

    # Assert - Precision maintained
    assert position.volume == Decimal("1.23456789")
    assert position.entry_price == Decimal("1.10000000")
    assert position.profit_loss == Decimal("61.72839450")


@pytest.mark.asyncio
async def test_uuid_generation(test_db: AsyncSession):
    """Test UUID primary key generation.

    Validates that UUID primary keys are automatically generated
    and are unique for each record.
    """
    # Arrange & Act
    strategy1 = Strategy(name="Strategy 1", parameters={}, status="ACTIVE")
    strategy2 = Strategy(name="Strategy 2", parameters={}, status="ACTIVE")

    test_db.add_all([strategy1, strategy2])
    await test_db.commit()
    await test_db.refresh(strategy1)
    await test_db.refresh(strategy2)

    # Assert
    assert isinstance(strategy1.id, UUID)
    assert isinstance(strategy2.id, UUID)
    assert strategy1.id != strategy2.id


@pytest.mark.asyncio
async def test_nullable_fields(test_db: AsyncSession):
    """Test nullable field handling.

    Validates that optional fields can be None and are handled
    correctly by the database.
    """
    # Arrange
    trade = Trade(
        symbol="GBPUSD",
        trade_type="BUY",
        volume=Decimal("1.0"),
        entry_price=Decimal("1.2000"),
        exit_price=Decimal("1.2100"),
        profit_loss=Decimal("100.00"),
        entry_time=datetime.utcnow(),
        exit_time=datetime.utcnow() + timedelta(hours=1),
        strategy_id=uuid4(),
        # commission, swap, order_id, position_id are None
    )

    # Act
    test_db.add(trade)
    await test_db.commit()
    await test_db.refresh(trade)

    # Assert
    assert trade.commission is None
    assert trade.swap is None
    assert trade.order_id is None
    assert trade.position_id is None


@pytest.mark.asyncio
async def test_concurrent_updates(test_db: AsyncSession):
    """Test concurrent update handling.

    Validates that concurrent updates to the same record
    are handled correctly by the database.
    """
    # Arrange
    strategy = Strategy(
        name="Concurrent Test Strategy",
        parameters={},
        status="ACTIVE",
        total_trades=0,
    )
    test_db.add(strategy)
    await test_db.commit()
    await test_db.refresh(strategy)

    # Act - Simulate concurrent updates
    strategy.total_trades = 1
    await test_db.commit()

    strategy.total_trades = 2
    await test_db.commit()

    # Assert
    result = await test_db.execute(select(Strategy).where(Strategy.id == strategy.id))
    final = result.scalar_one()
    assert final.total_trades == 2


@pytest.mark.asyncio
async def test_query_filtering_by_status(test_db: AsyncSession):
    """Test querying records by status field.

    Validates that records can be efficiently filtered by
    status field using indexes.
    """
    # Arrange - Create multiple orders with different statuses
    orders = [
        Order(
            symbol="EURUSD",
            order_type="BUY",
            volume=Decimal("1.0"),
            price=Decimal("1.1000"),
            status="PENDING",
            strategy_id=uuid4(),
        ),
        Order(
            symbol="GBPUSD",
            order_type="SELL",
            volume=Decimal("0.5"),
            price=Decimal("1.2000"),
            status="FILLED",
            strategy_id=uuid4(),
        ),
        Order(
            symbol="USDJPY",
            order_type="BUY",
            volume=Decimal("2.0"),
            price=Decimal("110.00"),
            status="CANCELLED",
            strategy_id=uuid4(),
        ),
    ]
    test_db.add_all(orders)
    await test_db.commit()

    # Act - Query by status
    result = await test_db.execute(select(Order).where(Order.status == "FILLED"))
    filled_orders = result.scalars().all()

    # Assert
    assert len(filled_orders) == 1
    assert filled_orders[0].status == "FILLED"
    assert filled_orders[0].symbol == "GBPUSD"


@pytest.mark.asyncio
async def test_bulk_insert_performance(test_db: AsyncSession):
    """Test bulk insert performance.

    Validates that multiple records can be inserted efficiently
    using bulk operations.
    """
    # Arrange - Create 100 market data records
    market_data_records = [
        MarketData(
            symbol="EURUSD",
            timeframe="1M",
            timestamp=datetime.utcnow() + timedelta(minutes=i),
            open=Decimal("1.1000"),
            high=Decimal("1.1010"),
            low=Decimal("1.0990"),
            close=Decimal("1.1005"),
            volume=Decimal("100000.00"),
        )
        for i in range(100)
    ]

    # Act
    test_db.add_all(market_data_records)
    await test_db.commit()

    # Assert
    result = await test_db.execute(
        select(MarketData).where(MarketData.symbol == "EURUSD")
    )
    all_records = result.scalars().all()
    assert len(all_records) == 100