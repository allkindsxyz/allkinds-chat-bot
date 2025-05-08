"""
Recovery utilities for fixing issues with the matching system.
"""
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.db.models import User, Match
from src.db.repositories import user_repo
from src.db.utils.state_persistence import load_critical_state, delete_critical_state


async def find_abandoned_matches(session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Find abandoned match operations based on persisted state.
    
    Args:
        session: Database session
        
    Returns:
        List of abandoned match states
    """
    from src.db.models import UserState
    import json
    
    try:
        # Find all states related to match operations
        query = select(UserState).where(UserState.state_data.like('%find_match_%'))
        result = await session.execute(query)
        states = result.scalars().all()
        
        abandoned_matches = []
        for state in states:
            try:
                # Parse the state data
                state_data = json.loads(state.state_data)
                
                # Check if it's an incomplete match operation
                if state_data.get("operation") in [
                    "find_match_started", 
                    "find_match_points_deducted"
                ]:
                    abandoned_matches.append({
                        "state_id": state.id,
                        "user_id": state.user_id,
                        "data": state_data,
                        "created_at": state.created_at,
                        "expires_at": state.expires_at
                    })
            except Exception as e:
                logger.error(f"Error parsing state {state.id}: {e}")
                continue
                
        return abandoned_matches
    except Exception as e:
        logger.error(f"Error finding abandoned matches: {e}")
        return []


async def recover_abandoned_match(session: AsyncSession, state_data: Dict[str, Any]) -> bool:
    """
    Attempt to recover an abandoned match operation.
    
    Args:
        session: Database session
        state_data: The state data for the abandoned match
        
    Returns:
        True if recovery was successful, False otherwise
    """
    try:
        user_id = state_data.get("user_id")
        if not user_id:
            logger.error(f"No user_id found in state data")
            return False
            
        # Get the user from database
        db_user = await user_repo.get(session, user_id)
        if not db_user:
            logger.error(f"User {user_id} not found in database")
            return False
            
        # Get the operation type and original points
        operation = state_data.get("operation")
        original_points = state_data.get("original_points")
        cost = state_data.get("cost", 0)
        
        if not original_points or not operation:
            logger.error(f"Missing required fields in state data: operation={operation}, original_points={original_points}")
            return False
            
        # Check if points need to be refunded
        if operation in ["find_match_started", "find_match_points_deducted"]:
            logger.info(f"Refunding {cost} points to user {user_id} from abandoned match operation")
            
            # Restore original points
            db_user.points = original_points
            session.add(db_user)
            await session.commit()
            
            # Delete the critical state
            await delete_critical_state(session, user_id)
            
            logger.info(f"Successfully refunded points for user {user_id}, new balance: {db_user.points}")
            return True
        else:
            logger.info(f"No points refund needed for operation: {operation}")
            return False
    except Exception as e:
        logger.error(f"Error recovering abandoned match: {e}")
        return False
        

async def recover_all_abandoned_matches(session: AsyncSession) -> Tuple[int, int]:
    """
    Recover all abandoned match operations.
    
    Args:
        session: Database session
        
    Returns:
        Tuple of (total_found, total_recovered)
    """
    try:
        # Find all abandoned matches
        abandoned_matches = await find_abandoned_matches(session)
        logger.info(f"Found {len(abandoned_matches)} abandoned match operations")
        
        # Recover each abandoned match
        recovered_count = 0
        for match_data in abandoned_matches:
            try:
                success = await recover_abandoned_match(session, match_data["data"])
                if success:
                    recovered_count += 1
            except Exception as e:
                logger.error(f"Error recovering match {match_data}: {e}")
                continue
                
        logger.info(f"Recovered {recovered_count} of {len(abandoned_matches)} abandoned match operations")
        return len(abandoned_matches), recovered_count
    except Exception as e:
        logger.error(f"Error recovering abandoned matches: {e}")
        return 0, 0


async def check_user_points_consistency(session: AsyncSession, user_id: int) -> bool:
    """
    Check and fix user points consistency based on match history.
    
    Args:
        session: Database session
        user_id: User ID to check
        
    Returns:
        True if fixes were applied, False otherwise
    """
    try:
        # Get the user
        db_user = await user_repo.get(session, user_id)
        if not db_user:
            logger.error(f"User {user_id} not found")
            return False
            
        # Get all matches initiated by this user (the one who paid for the match)
        query = select(Match).where(Match.user1_id == user_id)
        result = await session.execute(query)
        matches = result.scalars().all()
        
        # Calculate expected points spent on matches
        match_cost = 1  # Default cost per match
        total_match_cost = len(matches) * match_cost
        
        # Check if there's an outstanding refund point recovery operation
        critical_state = await load_critical_state(session, user_id)
        pending_refund = 0
        
        if critical_state and critical_state.get("operation") in ["find_match_started", "find_match_points_deducted"]:
            logger.info(f"Found pending refund for user {user_id}")
            pending_refund = critical_state.get("cost", 0)
            
        # Log the point analysis
        logger.info(f"User {user_id} analysis: current_points={db_user.points}, total_matches={len(matches)}, pending_refund={pending_refund}")
        
        # No inconsistency detected
        return False
    except Exception as e:
        logger.error(f"Error checking user points consistency: {e}")
        return False 