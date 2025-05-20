from typing import Any, Generic, Type, TypeVar

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base class for data access layer."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, session: AsyncSession, pk: Any) -> ModelType | None:
        """Get a single record by primary key."""
        return await session.get(self.model, pk)

    async def get_by_attribute(self, session: AsyncSession, attribute: str | None = None, value: Any = None, expression: Any | None = None) -> ModelType | None:
        """Get a single record by an attribute or a complex expression."""
        try:
            if expression is not None:
                stmt = select(self.model).where(expression)
            elif attribute is not None:
                stmt = select(self.model).where(getattr(self.model, attribute) == value)
            else:
                raise ValueError("Either attribute/value or expression must be provided")
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            if session:
                await session.rollback()
            raise

    async def create(self, session: AsyncSession, data: dict) -> ModelType:
        """Create a new record."""
        try:
            stmt = insert(self.model).values(**data).returning(self.model)
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one()
        except Exception as e:
            if session:
                await session.rollback()
            raise

    async def update(self, session: AsyncSession, pk: Any, data: dict) -> ModelType | None:
        """Update a record by primary key."""
        try:
            stmt = (
                update(self.model)
                .where(self.model.id == pk) # Assuming 'id' is the PK
                .values(**data)
                .returning(self.model)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one_or_none()
        except Exception as e:
            if session:
                await session.rollback()
            raise

    async def delete(self, session: AsyncSession, pk: Any) -> bool:
        """Delete a record by primary key."""
        try:
            stmt = delete(self.model).where(self.model.id == pk)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            if session:
                await session.rollback()
            raise

    async def get_or_create(
        self, session: AsyncSession, defaults: dict | None = None, **kwargs: Any
    ) -> tuple[ModelType, bool]:
        """Get a record or create it if it doesn't exist."""
        try:
            instance = await self.get_by_attribute(session, list(kwargs.keys())[0], list(kwargs.values())[0]) # Simple get based on first kwarg
            if instance:
                return instance, False
            data = kwargs.copy()
            if defaults:
                data.update(defaults)
            instance = await self.create(session, data)
            return instance, True
        except Exception as e:
            if session:
                await session.rollback()
            raise 