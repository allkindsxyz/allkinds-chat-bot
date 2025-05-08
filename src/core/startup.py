"""
Application startup tasks.
"""
import asyncio
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.db.utils.recovery import recover_all_abandoned_matches
from src.db.utils.state_persistence import clean_expired_states


async def run_startup_tasks():
    """
    Run critical startup tasks to ensure database integrity.
    - Recover abandoned match operations
    - Clean up expired states
    """
    logger.info("Starting database integrity checks...")
    
    # Use the session context manager
    try:
        async for session in get_session():
            await run_integrity_checks(session)
            break  # Exit after first successful session
    except Exception as e:
        logger.error(f"Error getting database session for startup tasks: {e}")
    
    logger.info("Database integrity checks completed.")


async def run_integrity_checks(session: AsyncSession):
    """
    Run database integrity checks.
    
    Args:
        session: Database session
    """
    try:
        # Recover abandoned match operations
        logger.info("Checking for abandoned match operations...")
        total, recovered = await recover_all_abandoned_matches(session)
        logger.info(f"Abandoned match recovery: found {total}, recovered {recovered}")
        
        # Clean up expired states
        logger.info("Cleaning up expired states...")
        cleaned = await clean_expired_states(session)
        logger.info(f"Cleaned {cleaned} expired states")
    except Exception as e:
        logger.error(f"Error running integrity checks: {e}")


# Coroutine to run the startup tasks
async def startup_coroutine():
    """
    Startup coroutine to be called from main.
    """
    await run_startup_tasks()
    

def startup_callback():
    """
    Synchronous callback for non-async startup hooks.
    """
    # Create a new event loop and run the startup tasks
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_startup_tasks())
    finally:
        loop.close() 