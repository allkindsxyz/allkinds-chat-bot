from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from loguru import logger
import yaml
import os

from src.db.models import User, Match, ChatMessage
from src.db.repositories import (
    user_repo, get_chat_by_participants,
    chat_message_repo, blocked_user_repo
)

_templates_cache = None

def get_text_template(key: str) -> str:
    global _templates_cache
    if _templates_cache is None:
        path = os.path.join(os.path.dirname(__file__), 'static', 'text_templates.yaml')
        with open(path, 'r', encoding='utf-8') as f:
            _templates_cache = yaml.safe_load(f)
    return _templates_cache.get(key, f"[No template for {key}]")

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
        chat_session = await get_chat_by_participants(session, user.id, partner_id, match.group_id)
        if not chat_session:
            pass  # chat_session creation removed
        
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
            "chat_id": chat_session.id if chat_session else None,
            "unread_count": unread_count,
            "telegram_user_id": await user_repo.get_telegram_user_id_by_id(partner.id),
            "username": partner.username,
        })
    
    return match_users


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