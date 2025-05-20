from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from loguru import logger

from src.db.models import User, Match, ChatMessage
from src.db.repositories import (
    user_repo, create_chat_session, get_by_match_id, get_partner_id,
    get_active_session_for_user, get_by_session_id, update_status,
    chat_message_repo, blocked_user_repo
)


async def get_user_matches(session: AsyncSession, user_id: int) -> list[dict]:
    """
    Get all matches for a user with chat information.
    
    Args:
        session: Database session
        user_id: User ID
        
    Returns:
        List of dictionaries with match information
    """
    # Make sure we have the internal user ID, not the telegram_user_id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    if not user:
        return []
    
    # Get all matches for this user
    query = (
        select(Match)
        .where(
            or_(
                Match.user1_id == user.id,
                Match.user2_id == user.id
            )
        )
        .order_by(Match.created_at.desc())
    )
    result = await session.execute(query)
    matches = result.scalars().all()
    
    # Get chat sessions and blocked users
    match_users = []
    blocked_users = await blocked_user_repo.get_blocked_users(session, user.id)
    blocked_user_ids = [b.blocked_user_id for b in blocked_users]
    
    for match in matches:
        # Determine partner ID
        partner_id = match.user2_id if match.user1_id == user.id else match.user1_id
        
        # Skip if partner is blocked
        if partner_id in blocked_user_ids:
            continue
        
        # Get partner user
        partner = await user_repo.get(session, partner_id)
        if not partner:
            continue
        
        # Get or create chat session
        chat_session = await get_by_match_id(session, match.id)
        if not chat_session:
            # Create a new chat session
            chat_session = await create_chat_session(
                session,
                initiator_id=user.id,
                recipient_id=partner_id,
                match_id=match.id
            )
        
        # Count unread messages
        unread_count = 0
        if chat_session:
            unread_count = await chat_message_repo.count_unread_messages(
                session,
                chat_session.id,
                user.id
            )
        
        # Format name
        partner_name = await get_partner_nickname(session, partner_id)
        
        match_users.append({
            "id": partner_id,
            "name": partner_name,
            "match_id": match.id,
            "chat_session_id": chat_session.id if chat_session else None,
            "unread_count": unread_count,
            "telegram_user_id": partner.telegram_user_id,
            "username": partner.username,
        })
    
    return match_users


async def get_active_chat_session(session: AsyncSession, user_id: int, partner_id: int) -> AnonymousChatSession:
    """
    Get or create an active chat session between two users.
    
    Args:
        session: Database session
        user_id: First user ID
        partner_id: Second user ID
        
    Returns:
        Chat session
    """
    # First check if there's an existing match
    query = (
        select(Match)
        .where(
            or_(
                and_(Match.user1_id == user_id, Match.user2_id == partner_id),
                and_(Match.user1_id == partner_id, Match.user2_id == user_id)
            )
        )
    )
    result = await session.execute(query)
    match = result.scalar_one_or_none()
    
    if not match:
        logger.warning(f"No match found between users {user_id} and {partner_id}")
        return None
    
    # Check if there's an existing chat session
    chat_session = await get_by_match_id(session, match.id)
    
    if chat_session:
        # If the chat session is not active, reactivate it
        if chat_session.status != "active":
            chat_session = await update_status(session, chat_session.id, "active")
        return chat_session
    else:
        # Create a new chat session
        return await create_chat_session(
            session,
            initiator_id=user_id,
            recipient_id=partner_id,
            match_id=match.id
        )


async def clean_inactive_chats(session: AsyncSession) -> int:
    """
    Clean up inactive chat sessions (older than 3 days).
    
    Args:
        session: Database session
        
    Returns:
        Number of chats cleaned up
    """
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    
    # Find inactive chats
    query = (
        select(AnonymousChatSession)
        .where(
            and_(
                AnonymousChatSession.status == "active",
                AnonymousChatSession.last_activity < three_days_ago
            )
        )
    )
    result = await session.execute(query)
    inactive_chats = result.scalars().all()
    
    # Mark them as ended
    count = 0
    for chat in inactive_chats:
        # Delete messages
        await chat_message_repo.delete_messages_for_chat(session, chat.id)
        
        # Update status
        await update_status(session, chat.id, "ended", set_ended=True)
        count += 1
    
    logger.info(f"Cleaned up {count} inactive chat sessions")
    return count


async def get_deep_link_payload(payload: str) -> tuple[int, int]:
    """
    Parse a deep link payload to extract match information.
    
    Args:
        payload: Deep link payload
        
    Returns:
        Tuple of (match_id, partner_id) or (None, None) if invalid
    """
    try:
        if payload.startswith("match_"):
            # Format: match_match_id_partner_id
            parts = payload.split("_")
            if len(parts) >= 3:
                match_id = int(parts[1])
                partner_id = int(parts[2])
                return match_id, partner_id
        elif payload.startswith("chat_"):
            # Format: chat_session_id
            # This section is handled directly in setup_chat_after_nickname
            # We just need to return a non-None value here to avoid showing the error
            return 0, 0
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing deep link payload: {e}")
    
    return None, None 