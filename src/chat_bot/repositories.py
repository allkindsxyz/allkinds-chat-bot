"""Repository functions for the chat bot."""
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass
from typing import List, Optional, Union, Any

from src.db.models import (
    User, Match, Chat,
    ChatMessage, BlockedUser,
    GroupMember
)
from src.db.repositories.user import user_repo
from src.db.repositories.match_repo import get_match_between_users
from src.db.repositories.chat_message_repo import chat_message_repo
from src.db.repositories.blocked_user_repo import blocked_user_repo


@dataclass
class ChatInfo:
    """Class to store chat information."""
    id: int
    initiator_id: int
    recipient_id: int
    status: str
    last_activity: Any = None


async def get_active_chats_for_user(session: AsyncSession, user_id: int) -> List[ChatInfo]:
    """
    Get all active chats for a user from the Chat table.
    
    Args:
        session: Database session
        user_id: ID of the user
        
    Returns:
        List of ChatInfo objects containing chat information
    """
    from loguru import logger
    
    # Query regular chats
    chat_query = select(Chat).where(
        and_(
            or_(
                Chat.initiator_id == user_id,
                Chat.recipient_id == user_id
            ),
            Chat.status == "active"
        )
    ).order_by(Chat.updated_at.desc())
    
    chat_result = await session.execute(chat_query)
    regular_chats = chat_result.scalars().all()
    logger.info(f"Found {len(regular_chats)} chats for user {user_id}")
    
    # Convert to ChatInfo objects
    result = []
    
    # Convert regular chats
    for chat in regular_chats:
        try:
            chat_info = ChatInfo(
                id=chat.id,
                initiator_id=chat.initiator_id,
                recipient_id=chat.recipient_id,
                status=chat.status,
                last_activity=chat.updated_at
            )
            result.append(chat_info)
            logger.info(f"Added chat: id={chat.id}")
        except Exception as e:
            logger.error(f"Error converting chat {chat.id}: {e}")
    
    logger.info(f"Total active chats: {len(result)}")
    return result


async def get_unread_message_count(session: AsyncSession, chat_id: int, user_id: int) -> int:
    """
    Count unread messages in a chat for a user.
    
    Args:
        session: Database session
        chat_id: ID of the chat session
        user_id: ID of the user
        
    Returns:
        Number of unread messages
    """
    query = select(ChatMessage).where(
        and_(
            ChatMessage.chat_session_id == chat_id,
            ChatMessage.sender_id != user_id,
            ChatMessage.is_read == False
        )
    )
    
    result = await session.execute(query)
    messages = result.scalars().all()
    return len(messages)


async def mark_messages_as_read(session: AsyncSession, chat_id: int, user_id: int) -> int:
    """
    Mark all messages in a chat as read for a user.
    
    Args:
        session: Database session
        chat_id: ID of the chat session
        user_id: ID of the user
        
    Returns:
        Number of messages marked as read
    """
    messages = await get_unread_messages(session, chat_id, user_id)
    count = 0
    
    for message in messages:
        message.is_read = True
        count += 1
    
    await session.commit()
    return count


async def get_unread_messages(session: AsyncSession, chat_id: int, user_id: int) -> list[ChatMessage]:
    """
    Get all unread messages in a chat for a user.
    
    Args:
        session: Database session
        chat_id: ID of the chat session
        user_id: ID of the user
        
    Returns:
        List of unread messages
    """
    query = select(ChatMessage).where(
        and_(
            ChatMessage.chat_session_id == chat_id,
            ChatMessage.sender_id != user_id,
            ChatMessage.is_read == False
        )
    ).order_by(ChatMessage.created_at.asc())
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_partner_nickname(session: AsyncSession, user_id: int) -> str:
    """
    Get nickname for a user from group_members.
    """
    result = await session.execute(select(GroupMember).where(GroupMember.user_id == user_id))
    group_member = result.scalar_one_or_none()
    if group_member and group_member.nickname:
        return group_member.nickname
    return f"User {user_id}"


async def end_chat_session(session: AsyncSession, chat_id: int) -> bool:
    """
    End a chat session by setting its status to 'ended'.
    
    Args:
        session: Database session
        chat_id: ID of the chat session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        chat = await session.get(Chat, chat_id)
        if chat:
            chat.status = "ended"
            await session.commit()
            return True
    except Exception as e:
        from loguru import logger
        logger.error(f"Error ending chat session: {e}")
    
    return False


async def get_unread_chat_summary(session: AsyncSession, user_id: int) -> List[dict]:
    """
    Get summary of unread messages for a user across all chats.
    
    Args:
        session: Database session
        user_id: ID of the user
        
    Returns:
        List of dicts with chat information and unread count
    """
    # Get all active chats for user
    all_chats = await get_active_chats_for_user(session, user_id)
    
    result = []
    for chat in all_chats:
        # Get partner ID
        partner_id = chat.recipient_id if chat.initiator_id == user_id else chat.initiator_id
        
        # Count unread messages
        unread_count = await get_unread_message_count(session, chat.id, user_id)
        
        # Only include chats with unread messages
        if unread_count > 0:
            partner_name = await get_partner_nickname(
                session, partner_id
            )
            
            result.append({
                "chat_id": chat.id,
                "partner_id": partner_id,
                "partner_name": partner_name,
                "unread_count": unread_count,
            })
    
    # Sort by unread count (highest first)
    result.sort(key=lambda x: x["unread_count"], reverse=True)
    
    return result 