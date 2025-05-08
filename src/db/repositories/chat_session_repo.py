from datetime import datetime
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
import secrets

from src.db.models import AnonymousChatSession, User, Match


async def create_chat_session(
    session: AsyncSession,
    initiator_id: int,
    recipient_id: int,
    match_id: int,
) -> AnonymousChatSession:
    """Create a new anonymous chat session between matched users."""
    # Generate unique session ID
    session_id = secrets.token_urlsafe(16)
    
    # Create chat session
    chat_session = AnonymousChatSession(
        session_id=session_id,
        initiator_id=initiator_id,
        recipient_id=recipient_id,
        match_id=match_id,
        status="pending"
    )
    
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    
    return chat_session


async def get_by_session_id(session: AsyncSession, session_id: str) -> AnonymousChatSession:
    """Get a chat session by its unique session ID."""
    query = select(AnonymousChatSession).where(AnonymousChatSession.session_id == session_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_by_match_id(session: AsyncSession, match_id: int) -> AnonymousChatSession:
    """
    Get a chat session by its match ID.
    Returns the most recent active session or the most recent session if no active ones exist.
    """
    # First try to find an active session
    active_query = (
        select(AnonymousChatSession)
        .where(
            and_(
                AnonymousChatSession.match_id == match_id,
                AnonymousChatSession.status == "active"
            )
        )
        .order_by(AnonymousChatSession.created_at.desc())
    )
    active_result = await session.execute(active_query)
    # Use first() instead of scalar_one_or_none() to avoid MultipleResultsFound error
    active_session = active_result.scalars().first()
    
    if active_session:
        return active_session
    
    # If no active session, get the most recent one
    recent_query = (
        select(AnonymousChatSession)
        .where(AnonymousChatSession.match_id == match_id)
        .order_by(AnonymousChatSession.created_at.desc())
    )
    recent_result = await session.execute(recent_query)
    # Use first() instead of scalar_one_or_none() to avoid MultipleResultsFound error
    return recent_result.scalars().first()


async def get_active_session_for_user(session: AsyncSession, user_id: int) -> AnonymousChatSession:
    """Get the active chat session for a user."""
    query = select(AnonymousChatSession).where(
        and_(
            (AnonymousChatSession.initiator_id == user_id) | (AnonymousChatSession.recipient_id == user_id),
            AnonymousChatSession.status == "active"
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def update_status(
    session: AsyncSession, 
    chat_session_id: int, 
    status: str, 
    set_ended: bool = False
) -> AnonymousChatSession:
    """Update the status of a chat session."""
    values = {"status": status}
    if set_ended and status == "ended":
        values["ended_at"] = datetime.utcnow()
        
    query = (
        update(AnonymousChatSession)
        .where(AnonymousChatSession.id == chat_session_id)
        .values(**values)
        .returning(AnonymousChatSession)
    )
    
    result = await session.execute(query)
    await session.commit()
    
    return result.scalar_one()


async def get_partner_id(session: AsyncSession, chat_session_id: int, user_id: int) -> int:
    """
    Get the partner ID for a user in a chat session.
    
    Args:
        session: Database session
        chat_session_id: ID of the chat session
        user_id: ID of the user
        
    Returns:
        The ID of the partner user
    """
    query = select(AnonymousChatSession).where(AnonymousChatSession.id == chat_session_id)
    result = await session.execute(query)
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        return None
        
    if chat_session.initiator_id == user_id:
        return chat_session.recipient_id
    elif chat_session.recipient_id == user_id:
        return chat_session.initiator_id
    else:
        return None  # User not part of this chat 