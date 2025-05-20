from datetime import datetime
import traceback
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models import Match, User
from src.core.diagnostics import track_db, IS_RAILWAY
from loguru import logger
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Tuple, Dict, Any

from src.core.config import get_settings
from src.core.diagnostics import track_db
from src.db.utils.session_management import ensure_active_session, with_retry

# Get settings for constants
settings = get_settings()
# Use IS_RAILWAY directly from diagnostics module


@track_db
async def create_match(
    session: AsyncSession,
    user1_id: int,
    user2_id: int,
    group_id: int,
    common_questions: int = 0,
) -> Match:
    """Create a new match between two users."""
    match = Match(
        user1_id=user1_id,
        user2_id=user2_id,
        group_id=group_id,
        common_questions=common_questions,
    )
    
    session.add(match)
    await session.commit()
    await session.refresh(match)
    
    return match


@track_db
async def get_by_id(session: AsyncSession, match_id: int) -> Match:
    """Get a match by its ID."""
    query = select(Match).where(Match.id == match_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


@track_db
async def get_with_users(session: AsyncSession, match_id: int) -> Match:
    """Get a match with its related users."""
    query = (
        select(Match)
        .where(Match.id == match_id)
        .options(joinedload(Match.user1), joinedload(Match.user2))
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


@track_db
async def get_matches_for_user(session: AsyncSession, user_id: int) -> list[Match]:
    """Get all matches for a user."""
    query = (
        select(Match)
        .where(or_(Match.user1_id == user_id, Match.user2_id == user_id))
        .order_by(Match.created_at.desc())
    )
    result = await session.execute(query)
    return result.scalars().all()


@track_db
async def get_match_between_users(session: AsyncSession, user1_id: int, user2_id: int) -> Match:
    """Check if there's already a match between two users."""
    query = (
        select(Match)
        .where(
            or_(
                (Match.user1_id == user1_id) & (Match.user2_id == user2_id),
                (Match.user1_id == user2_id) & (Match.user2_id == user1_id)
            )
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


@track_db
@with_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
async def find_matches(session: AsyncSession, user_id: int, group_id: int) -> list:
    print(f"DEBUG_MATCH: find_matches called with user_id={user_id}, group_id={group_id}")
    logger.info(f"DEBUG_MATCH: find_matches called with user_id={user_id}, group_id={group_id}")
    """
    Find potential matches for a user in a group.
    
    Args:
        session: Database session
        user_id: ID of the user to find matches for
        group_id: ID of the group to find matches in
        
    Returns:
        A list of tuples containing (matched_user_id, cohesion_score, common_questions, category_scores, category_counts)
        The list is sorted by cohesion_score in descending order.
    """
    logger.info(f"[DEBUG_MATCH_DB] find_matches called with user_id={user_id}, group_id={group_id}")
    
    # For Railway debugging, log the session state
    if IS_RAILWAY:
        logger.info(f"RAILWAY DB DEBUG: Session info - id={id(session)}, is_active={session.is_active}")
    
    try:
        from src.db.models import GroupMember, User
        from src.bot.utils.matching import calculate_cohesion_scores
        
        logger.info(f"Starting find_matches for user {user_id} in group {group_id}")
        
        # Ensure we have a clean session state - commit any pending changes
        try:
            if session.is_active:
                await session.commit()
                logger.info("Session committed before starting match search")
        except Exception as commit_error:
            logger.error(f"Error committing session before match search: {commit_error}")
        
        # Get all other active users in the same group
        query = (
            select(User.id)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(
                GroupMember.group_id == group_id,
                GroupMember.user_id != user_id,
                User.is_active == True
            )
        )
        
        try:
            # Ensure session is active before executing query
            session = await ensure_active_session(session)
            result = await session.execute(query)
            potential_matches = result.scalars().all()
            
            logger.info(f"Found {len(potential_matches)} potential matches for user {user_id} in group {group_id}")
            
            # Extra Railway logging
            if IS_RAILWAY:
                logger.info(f"RAILWAY DB DEBUG: potential_matches query SQL = {str(query)}")
                logger.info(f"RAILWAY DB DEBUG: potential_matches = {potential_matches}")
                
        except Exception as db_error:
            logger.error(f"Database error when finding potential matches: {str(db_error)}")
            if IS_RAILWAY:
                logger.error(f"RAILWAY DB ERROR: {str(db_error)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        
        # If no potential matches, return early
        if not potential_matches:
            logger.info(f"No potential matches found for user {user_id} in group {group_id}")
            return []
            
        # Calculate cohesion scores with each potential match
        match_results = []
        for potential_match_id in potential_matches:
            try:
                # Ensure session is active before calculating cohesion
                session = await ensure_active_session(session)
                
                cohesion_score, common_questions, category_scores, category_counts = await calculate_cohesion_scores(
                    session, user_id, potential_match_id, group_id
                )
                
                # Only include if they have common questions and meet minimum threshold
                if common_questions >= 3:  # Using the same threshold as MIN_SHARED_QUESTIONS
                    match_results.append((
                        potential_match_id,  # matched user ID
                        cohesion_score,      # overall cohesion score
                        common_questions,    # number of common questions
                        category_scores,     # dictionary of category scores
                        category_counts      # dictionary of question counts per category
                    ))
                    logger.debug(f"Match with user {potential_match_id}: questions={common_questions}")
            except Exception as e:
                logger.error(f"Error calculating cohesion with user {potential_match_id}: {e}")
                if IS_RAILWAY:
                    logger.error(f"RAILWAY ERROR in calculate_cohesion_scores: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                continue
        
        # Sort by cohesion score (highest first)
        match_results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Found {len(match_results)} valid matches for user {user_id} in group {group_id}")
        return match_results
    except Exception as e:
        logger.error(f"Error in find_matches: {e}")
        if IS_RAILWAY:
            logger.error(f"RAILWAY ERROR in find_matches: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        return []


@track_db
async def get_match(session: AsyncSession, user1_id: int, user2_id: int, group_id: int) -> Match:
    """
    Get a match between two users in a specific group.
    
    Args:
        session: Database session
        user1_id: ID of the first user
        user2_id: ID of the second user
        group_id: ID of the group
        
    Returns:
        Match object if found, None otherwise
    """
    query = (
        select(Match)
        .where(
            Match.group_id == group_id,
            (
                ((Match.user1_id == user1_id) & (Match.user2_id == user2_id)) |
                ((Match.user1_id == user2_id) & (Match.user2_id == user1_id))
            )
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() 