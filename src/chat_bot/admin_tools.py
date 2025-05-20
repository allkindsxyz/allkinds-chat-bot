"""
Admin utilities for the chat bot.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.db.repositories.chat_message_repo import chat_message_repo


async def delete_all_chats(session: AsyncSession) -> int:
    """
    Delete all active chat sessions.
    
    Args:
        session: Database session
        
    Returns:
        Number of chats deleted
    """
    # Find all active chats
    query = select(AnonymousChatSession).where(AnonymousChatSession.status == "active")
    result = await session.execute(query)
    active_chats = result.scalars().all()
    
    count = 0
    for chat in active_chats:
        # Delete all messages
        deleted_messages = await chat_message_repo.delete_messages_for_chat(session, chat.id)
        logger.info(f"Deleted {deleted_messages} messages from chat {chat.id}")
        
        # Mark chat as ended
        await update_status(session, chat.id, "ended", set_ended=True)
        count += 1
    
    logger.info(f"Deleted {count} active chat sessions")
    return count 