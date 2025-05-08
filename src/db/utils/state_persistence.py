"""
Utilities for state persistence and recovery.
"""
from typing import Dict, Any, Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete

from src.db.models import UserState


async def save_critical_state(session: AsyncSession, user_id: int, state_data: Dict[str, Any], ttl_seconds: int = 3600) -> bool:
    """
    Save critical state data to the database to survive application restarts.
    
    Args:
        session: Database session
        user_id: ID of the user
        state_data: Dictionary of state data to store
        ttl_seconds: Time-to-live in seconds (default: 1 hour)
        
    Returns:
        True if state was saved successfully, False otherwise
    """
    try:
        # Check if there's an existing state for this user
        query = select(UserState).where(UserState.user_id == user_id)
        result = await session.execute(query)
        existing_state = result.scalar_one_or_none()
        
        # Serialize the state data to JSON-compatible format
        import json
        serialized_data = json.dumps(state_data)
        
        # Calculate expiration time
        from datetime import datetime, timedelta
        expiration = datetime.now() + timedelta(seconds=ttl_seconds)
        
        if existing_state:
            # Update existing state
            existing_state.state_data = serialized_data
            existing_state.expires_at = expiration
            existing_state.updated_at = datetime.now()
            session.add(existing_state)
        else:
            # Create new state
            new_state = UserState(
                user_id=user_id,
                state_data=serialized_data,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                expires_at=expiration
            )
            session.add(new_state)
            
        await session.commit()
        logger.info(f"Saved critical state for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save critical state for user {user_id}: {e}")
        return False


async def load_critical_state(session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Load critical state data from the database.
    
    Args:
        session: Database session
        user_id: ID of the user
        
    Returns:
        Dictionary of state data or None if not found or expired
    """
    try:
        # Check if there's an existing state for this user
        query = select(UserState).where(UserState.user_id == user_id)
        result = await session.execute(query)
        existing_state = result.scalar_one_or_none()
        
        if not existing_state:
            logger.info(f"No saved state found for user {user_id}")
            return None
            
        # Check if state has expired
        from datetime import datetime
        if existing_state.expires_at < datetime.now():
            logger.info(f"Saved state for user {user_id} has expired")
            # Remove expired state
            await session.delete(existing_state)
            await session.commit()
            return None
            
        # Deserialize the state data
        import json
        state_data = json.loads(existing_state.state_data)
        
        logger.info(f"Loaded critical state for user {user_id}")
        return state_data
    except Exception as e:
        logger.error(f"Failed to load critical state for user {user_id}: {e}")
        return None


async def delete_critical_state(session: AsyncSession, user_id: int) -> bool:
    """
    Delete critical state data from the database.
    
    Args:
        session: Database session
        user_id: ID of the user
        
    Returns:
        True if state was deleted successfully, False otherwise
    """
    try:
        # Delete state for this user
        stmt = delete(UserState).where(UserState.user_id == user_id)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Deleted critical state for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete critical state for user {user_id}: {e}")
        return False


async def clean_expired_states(session: AsyncSession) -> int:
    """
    Clean up expired states from the database.
    
    Args:
        session: Database session
        
    Returns:
        Number of expired states removed
    """
    try:
        from datetime import datetime
        
        # Delete all expired states
        stmt = delete(UserState).where(UserState.expires_at < datetime.now())
        result = await session.execute(stmt)
        count = result.rowcount
        
        await session.commit()
        logger.info(f"Cleaned up {count} expired states")
        return count
    except Exception as e:
        logger.error(f"Failed to clean up expired states: {e}")
        return 0 