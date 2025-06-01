from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.repositories.base import BaseRepository
from src.core.config import get_redis_client
from loguru import logger


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    async def get_id_by_telegram_user_id(self, telegram_user_id: int) -> int | None:
        redis = get_redis_client()
        user_id = await redis.get(f"user:id:{telegram_user_id}")
        logger.info(f"[DEBUG][user_repo] Redis lookup: user:id:{telegram_user_id} -> {user_id}")
        return int(user_id) if user_id else None

    async def get_telegram_user_id_by_id(self, user_id: int) -> int | None:
        redis = get_redis_client()
        tg_id = await redis.get(f"user:tgid:{user_id}")
        return int(tg_id) if tg_id else None

    async def set_user_id_mapping(self, user_id: int, telegram_user_id: int) -> None:
        redis = get_redis_client()
        await redis.set(f"user:id:{telegram_user_id}", user_id)
        await redis.set(f"user:tgid:{user_id}", telegram_user_id)

    async def get_by_telegram_user_id(self, session: AsyncSession, telegram_user_id: int) -> User | None:
        user_id = await self.get_id_by_telegram_user_id(telegram_user_id)
        if not user_id:
            return None
        return await self.get(session, user_id)

    async def get_or_create_user(
        self, session: AsyncSession, telegram_user: dict
    ) -> tuple[User, bool]:
        """Gets or creates a user based on Telegram user info."""
        # Сначала ищем по telegram_user_id через Redis
        user_id = await self.get_id_by_telegram_user_id(telegram_user["id"])
        if user_id:
            user = await self.get(session, user_id)
            return user, False if user else (None, False)
        # Создаём пользователя
        user = await self.create(
            session,
            username=telegram_user.get("username"),
            is_active=True,
            points=0,
        )
        await self.set_user_id_mapping(user.id, telegram_user["id"])
        return user, True
    
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