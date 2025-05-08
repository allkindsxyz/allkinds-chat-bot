from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware, types
from aiogram.types import TelegramObject, Update
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from datetime import datetime, timedelta
import os

from src.core.config import get_settings
from src.db.models import AnonymousChatSession
from src.db.repositories.user import user_repo
from src.db.base import get_async_engine


class DatabaseMiddleware(BaseMiddleware):
    """Middleware for handling database connections with proper error handling and timeouts."""
    
    def __init__(self):
        self.session_pool = {}
        self.retry_attempts = 3
        self.session_timeout = 10  # Reduce timeout from 30 to 10 seconds
        logger.info("Database middleware initialized with retry logic")
        super().__init__()
    
    async def __call__(self, handler, event, data):
        import time
        import asyncio
        from sqlalchemy.exc import SQLAlchemyError
        
        # Create a new session for this request with retry logic
        session = None
        engine = None
        
        # Store original exception if we need to re-raise later
        original_exc = None
        
        for attempt in range(self.retry_attempts):
            try:
                # Get or create engine with proper error handling
                try:
                    engine = get_async_engine()
                except Exception as e:
                    logger.error(f"Failed to create database engine: {e}")
                    # Continue without a database session instead of raising
                    # This allows commands like /start, /help to still work even with DB issues
                    return await handler(event, data)
                
                # Create session with timeout
                async_session = async_sessionmaker(
                    engine, expire_on_commit=False, class_=AsyncSession
                )
                
                # Create session with timeout protection
                try:
                    # Get a session factory - FIX: Don't call it as a function, just pass the factory
                    session_factory = async_session
                    
                    # Create a real session from the factory
                    session = session_factory()
                    
                    # Add session to the data dict
                    data["session"] = session
                    
                    # Process handler
                    result = await handler(event, data)
                    
                    # Close session
                    await session.close()
                    return result
                    
                except asyncio.TimeoutError:
                    logger.error(f"Session creation timed out after {self.session_timeout}s (attempt {attempt+1}/{self.retry_attempts})")
                    if session:
                        await session.close()
                    # Try again on timeout
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(1)  # Shorter delay for retries (was 2**attempt)
                        continue
                    else:
                        # Fall through to handler without session on final timeout
                        return await handler(event, data)
                    
            except asyncio.exceptions.CancelledError as e:
                logger.warning(f"Database connection cancelled (attempt {attempt+1}/{self.retry_attempts}): {e}")
                original_exc = e
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(1)  # Shorter delay
                    continue
                    
            except SQLAlchemyError as e:
                logger.error(f"Database error (attempt {attempt+1}/{self.retry_attempts}): {e}")
                original_exc = e
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(1)  # Shorter delay
                    continue
                    
            except Exception as e:
                logger.error(f"Unexpected error in database middleware (attempt {attempt+1}/{self.retry_attempts}): {e}")
                original_exc = e
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(1)  # Shorter delay
                    continue
                    
        # All retries failed - just proceed without a database session
        logger.warning(f"Database connection failed after {self.retry_attempts} retries, proceeding without session")
        
        # Continue with handler even without database to prevent bot from becoming unresponsive
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging bot events and user actions."""
    
    def __init__(self):
        super().__init__()
        logger.info("Logging middleware initialized")
    
    async def __call__(self, handler, event, data):
        # Get user info if available
        user_id = None
        
        if hasattr(event, 'message') and event.message:
            user_id = event.message.from_user.id if event.message.from_user else None
        elif hasattr(event, 'callback_query') and event.callback_query:
            user_id = event.callback_query.from_user.id if event.callback_query.from_user else None
        
        # Update activity timestamp for user's active chats
        session = data.get("session")
        if user_id and session:
            try:
                # Get user from DB
                user = await user_repo.get_by_telegram_id(session, user_id)
                if user:
                    # Find active chat sessions for this user
                    from sqlalchemy import select, or_, and_
                    query = select(AnonymousChatSession).where(
                        and_(
                            or_(
                                AnonymousChatSession.initiator_id == user.id,
                                AnonymousChatSession.recipient_id == user.id
                            ),
                            AnonymousChatSession.status == "active"
                        )
                    )
                    result = await session.execute(query)
                    chat_sessions = result.scalars().all()
                    
                    # Update last activity
                    for chat in chat_sessions:
                        chat.last_activity = datetime.utcnow()
                    
                    await session.commit()
            except Exception as e:
                logger.warning(f"Failed to update chat activity: {e}")
        
        return await handler(event, data)


class BotMiddleware(BaseMiddleware):
    """Middleware to inject the bot instance into handler calls."""
    
    def __init__(self, bot_instance=None):
        """Initialize with a bot instance."""
        self.bot = bot_instance
        super().__init__()
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Inject bot instance into handler call."""
        # If bot instance was provided in the constructor, add it to data
        if self.bot:
            data["bot"] = self.bot
        return await handler(event, data) 