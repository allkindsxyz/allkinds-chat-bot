from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> User | None:
        return await self.get_by_attribute(session, "telegram_id", telegram_id)

    async def get_or_create_user(
        self, session: AsyncSession, telegram_user: dict
    ) -> tuple[User, bool]:
        """Gets or creates a user based on Telegram user info."""
        return await self.get_or_create(
            session,
            telegram_id=telegram_user["id"],
            defaults={
                "username": telegram_user.get("username"),
                "is_active": True,
                "points": 0,
            }
        )
    
    async def add_points(self, session: AsyncSession, user_id: int, points: int) -> User | None:
        """Add points to a user."""
        user = await self.get(session, user_id)
        if not user:
            return None
        
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(points=User.points + points)
            .returning(User)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()
    
    async def subtract_points(self, session: AsyncSession, user_id: int, points: int) -> User | None:
        """Subtract points from a user."""
        user = await self.get(session, user_id)
        if not user:
            return None
        
        # Don't allow negative points
        if user.points < points:
            return user
        
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(points=User.points - points)
            .returning(User)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()
    
    async def get_points(self, session: AsyncSession, user_id: int) -> int:
        """Get a user's current points."""
        user = await self.get(session, user_id)
        return user.points if user else 0

user_repo = UserRepository() 