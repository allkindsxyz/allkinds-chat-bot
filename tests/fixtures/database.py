import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event

from src.db.base import Base
from src.db.models import User, Match, ChatMessage

@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def test_session_maker(test_engine):
    """Create a session factory for the test database."""
    return sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

@pytest.fixture
async def test_session(test_session_maker):
    """Create a new session for a test."""
    async with test_session_maker() as session:
        yield session

@pytest.fixture
async def test_user(test_session):
    """Create a test user in the database."""
    user = User(
        telegram_id=123456789,
        first_name="Test",
        last_name="User",
        username="testuser",
    )
    test_session.add(user)
    await test_session.commit()
    return user

@pytest.fixture
async def test_user2(test_session):
    """Create a second test user in the database."""
    user = User(
        telegram_id=987654321,
        first_name="Another",
        last_name="User",
        username="anotheruser",
    )
    test_session.add(user)
    await test_session.commit()
    return user

@pytest.fixture
async def test_match(test_session, test_user, test_user2):
    """Create a test match between users."""
    match = Match(
        user1_id=test_user.id,
        user2_id=test_user2.id,
        group_id=1,
    )
    test_session.add(match)
    await test_session.commit()
    return match 