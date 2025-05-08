import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event

from src.db.base import Base
from src.db.models import User, Group, Question, Answer, GroupMember, MemberRole

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
async def test_group(test_session, test_user):
    """Create a test group in the database."""
    group = Group(
        name="Test Group",
        description="A test group for automated testing",
        creator_id=test_user.id,
    )
    test_session.add(group)
    await test_session.commit()
    
    # Add the user as an admin of the group
    member = GroupMember(
        user_id=test_user.id,
        group_id=group.id,
        role=MemberRole.ADMIN,
    )
    test_session.add(member)
    await test_session.commit()
    
    return group

@pytest.fixture
async def test_question(test_session, test_user, test_group):
    """Create a test question in the database."""
    question = Question(
        text="Is this a test question?",
        author_id=test_user.id,
        group_id=test_group.id,
        category="Test",
    )
    test_session.add(question)
    await test_session.commit()
    return question 