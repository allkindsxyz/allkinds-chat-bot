from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import BlockedUser
from src.db.repositories.base import BaseRepository


class BlockedUserRepository(BaseRepository[BlockedUser]):
    """Repository for blocked users."""
    
    def __init__(self):
        super().__init__(BlockedUser)
    
    async def block_user(
        self,
        session: AsyncSession,
        user_id: int,
        blocked_user_id: int,
    ) -> BlockedUser:
        """
        Block a user.
        
        Args:
            session: Database session
            user_id: ID of the user doing the blocking
            blocked_user_id: ID of the user being blocked
            
        Returns:
            The created blocked user relationship
        """
        # Check if already blocked
        existing = await self.is_blocked(session, user_id, blocked_user_id)
        if existing:
            return existing
            
        blocked = await self.create(
            session,
            data={
                "user_id": user_id,
                "blocked_user_id": blocked_user_id,
            }
        )
        await session.commit()
        await session.refresh(blocked)
        
        return blocked
    
    async def unblock_user(
        self,
        session: AsyncSession,
        user_id: int,
        blocked_user_id: int,
    ) -> bool:
        """
        Unblock a user.
        
        Args:
            session: Database session
            user_id: ID of the user doing the unblocking
            blocked_user_id: ID of the user being unblocked
            
        Returns:
            True if successfully unblocked, False if not found
        """
        query = (
            delete(BlockedUser)
            .where(
                (BlockedUser.user_id == user_id) &
                (BlockedUser.blocked_user_id == blocked_user_id)
            )
        )
        result = await session.execute(query)
        await session.commit()
        
        return result.rowcount > 0
    
    async def is_blocked(
        self,
        session: AsyncSession,
        user_id: int,
        blocked_user_id: int,
    ) -> BlockedUser:
        """
        Check if a user is blocked by another user.
        
        Args:
            session: Database session
            user_id: ID of the user who may have blocked
            blocked_user_id: ID of the user who may be blocked
            
        Returns:
            The BlockedUser object if blocked, None otherwise
        """
        query = (
            select(BlockedUser)
            .where(
                (BlockedUser.user_id == user_id) &
                (BlockedUser.blocked_user_id == blocked_user_id)
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_blocked_users(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> list[BlockedUser]:
        """
        Get all users blocked by a user.
        
        Args:
            session: Database session
            user_id: ID of the user
            
        Returns:
            List of blocked user relationships
        """
        query = (
            select(BlockedUser)
            .where(BlockedUser.user_id == user_id)
            .order_by(BlockedUser.created_at.desc())
        )
        result = await session.execute(query)
        return result.scalars().all()


blocked_user_repo = BlockedUserRepository() 