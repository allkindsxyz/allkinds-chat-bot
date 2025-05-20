import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.base import Base, SQLALCHEMY_DATABASE_URL
from src.db.models import User, Group, GroupMember, MemberRole
from src.core.config import get_settings

settings = get_settings()

async def init_dev_data():
    """Initialize development data with a test user and group."""
    logger.info("Initializing development data...")
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Create a test user
        test_user = User(
            telegram_id=179382367,  # Your Telegram ID from .env
            username="test_user",
            first_name="Test",
            last_name="User",
            is_active=True,
            is_admin=True
        )
        
        # Create a test group
        test_group = Group(
            name="Development Team",
            description="Group for development and testing",
            creator_id=1,  # Will be updated after user creation
            is_active=True,
            is_private=False
        )
        
        # Add to session and commit
        conn.add(test_user)
        await conn.commit()
        
        # Update group creator_id with the new user's ID
        test_group.creator_id = test_user.id
        conn.add(test_group)
        await conn.commit()
        
        # Create group membership
        group_member = GroupMember(
            group_id=test_group.id,
            user_id=test_user.id,
            role=MemberRole.CREATOR
        )
        conn.add(group_member)
        await conn.commit()
    
    await engine.dispose()
    logger.info("Development data initialized.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_dev_data()) 