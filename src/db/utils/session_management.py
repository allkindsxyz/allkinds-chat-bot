"""
Utilities for database session management and retry logic.
"""
import asyncio
import functools
from typing import Callable, TypeVar, Any, Awaitable
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, DatabaseError

from src.db.base import get_session, async_session_factory

T = TypeVar('T')

async def get_fresh_session() -> AsyncSession:
    """
    Get a fresh database session.
    
    Returns:
        A new AsyncSession object.
    """
    try:
        # Using the existing get_session function as an async generator
        async for session in get_session():
            return session
    except Exception as e:
        logger.error(f"Error creating new database session: {e}")
        raise

async def ensure_active_session(session: AsyncSession) -> AsyncSession:
    """
    Ensure that a session is active, creating a new one if necessary.
    
    Args:
        session: The session to check
        
    Returns:
        An active session (either the original or a new one)
    """
    try:
        if session and session.is_active:
            return session
        
        logger.warning("Session is not active, creating a new one")
        return await get_fresh_session()
    except Exception as e:
        logger.error(f"Error ensuring active session: {e}")
        raise

def with_retry(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 10.0
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to retry async database operations with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Try to ensure we have an active session if one is passed
                    if 'session' in kwargs and kwargs['session'] is not None:
                        kwargs['session'] = await ensure_active_session(kwargs['session'])
                    
                    return await func(*args, **kwargs)
                except (SQLAlchemyError, DatabaseError) as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        
                        # Add some jitter (±10%)
                        jitter = 0.1 * delay * (2 * asyncio.get_event_loop().time() % 1 - 0.5)
                        delay += jitter
                        
                        logger.warning(f"Database operation failed (attempt {attempt}/{max_attempts}): {e}. Retrying in {delay:.2f}s")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Database operation failed after {max_attempts} attempts: {e}")
                        raise last_exception
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected error in retry logic")
            
        return wrapper
    return decorator

async def with_transaction_lock(session: AsyncSession, lock_key: str, timeout: float = 10.0) -> bool:
    """
    Acquire a database-level lock for a specific key.
    
    Args:
        session: Database session
        lock_key: Unique key for the lock
        timeout: Timeout in seconds
        
    Returns:
        True if lock was acquired, False otherwise
    """
    try:
        # Try to acquire a PostgreSQL advisory lock
        # This is a simplified version - in production you might want to use a more robust locking mechanism
        result = await session.execute(
            f"SELECT pg_try_advisory_lock(hashtext('{lock_key}'))"
        )
        acquired = result.scalar()
        
        if acquired:
            logger.debug(f"Acquired lock for {lock_key}")
        else:
            logger.warning(f"Failed to acquire lock for {lock_key}")
            
        return acquired
    except Exception as e:
        logger.error(f"Error acquiring lock: {e}")
        return False

async def release_transaction_lock(session: AsyncSession, lock_key: str) -> bool:
    """
    Release a previously acquired database-level lock.
    
    Args:
        session: Database session
        lock_key: The key used to acquire the lock
        
    Returns:
        True if lock was released, False otherwise
    """
    try:
        # Release the PostgreSQL advisory lock
        result = await session.execute(
            f"SELECT pg_advisory_unlock(hashtext('{lock_key}'))"
        )
        released = result.scalar()
        
        if released:
            logger.debug(f"Released lock for {lock_key}")
        else:
            logger.warning(f"Failed to release lock for {lock_key} (possibly not owned by this connection)")
            
        return released
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")
        return False 