from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ChatMessage, User
from src.db.repositories.base import BaseRepository


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Repository for chat messages."""
    
    def __init__(self):
        super().__init__(ChatMessage)
    
    async def create_message(
        self,
        session: AsyncSession,
        chat_id: int,
        sender_id: int,
        content_type: str,
        text_content: str = None,
        file_id: str = None,
    ) -> ChatMessage:
        """
        Create a new chat message.
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            sender_id: ID of the message sender
            content_type: Type of content (text, photo, sticker, etc.)
            text_content: Text content of the message (for text messages)
            file_id: File ID (for media messages)
            
        Returns:
            The created message
        """
        message = await self.create(
            session,
            data={
                "chat_id": chat_id,
                "sender_id": sender_id,
                "content_type": content_type,
                "text_content": text_content,
                "file_id": file_id,
                "is_read": False,
            }
        )
        await session.commit()
        await session.refresh(message)
        
        return message
    
    async def get_chat_messages(
        self,
        session: AsyncSession,
        chat_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatMessage]:
        """
        Get messages for a chat session, ordered by creation time (newest first).
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            limit: Maximum number of messages to return
            offset: Number of messages to skip (for pagination)
            
        Returns:
            List of messages
        """
        query = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        return result.scalars().all()
    
    async def mark_messages_as_read(
        self,
        session: AsyncSession,
        chat_id: int,
        user_id: int,
    ) -> int:
        """
        Mark all unread messages in a chat session as read for a specific user.
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            user_id: ID of the user reading the messages
            
        Returns:
            Number of messages marked as read
        """
        # Only mark messages sent by others as read (not user's own messages)
        query = (
            update(ChatMessage)
            .where(
                (ChatMessage.chat_id == chat_id) &
                (ChatMessage.sender_id != user_id) &
                (ChatMessage.is_read == False)
            )
            .values(is_read=True)
        )
        result = await session.execute(query)
        await session.commit()
        
        return result.rowcount
    
    async def count_unread_messages(
        self,
        session: AsyncSession,
        chat_id: int,
        user_id: int,
    ) -> int:
        """
        Count unread messages in a chat session for a specific user.
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            user_id: ID of the user
            
        Returns:
            Number of unread messages
        """
        query = (
            select(func.count())
            .where(
                (ChatMessage.chat_id == chat_id) &
                (ChatMessage.sender_id != user_id) &
                (ChatMessage.is_read == False)
            )
        )
        result = await session.execute(query)
        return result.scalar_one() or 0
    
    async def delete_messages_for_chat(
        self,
        session: AsyncSession,
        chat_id: int,
    ) -> int:
        """
        Delete all messages for a chat session.
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            
        Returns:
            Number of deleted messages
        """
        query = select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        result = await session.execute(query)
        messages = result.scalars().all()
        
        for message in messages:
            await session.delete(message)
        
        await session.commit()
        return len(messages)
    
    async def count_chat_messages(
        self,
        session: AsyncSession,
        chat_id: int,
    ) -> int:
        """
        Count total number of messages in a chat session.
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            
        Returns:
            Number of messages
        """
        query = (
            select(func.count())
            .where(ChatMessage.chat_id == chat_id)
        )
        result = await session.execute(query)
        return result.scalar_one() or 0
    
    async def get_latest_message(
        self,
        session: AsyncSession,
        chat_id: int,
    ) -> ChatMessage:
        """
        Get the latest message from a chat session.
        
        Args:
            session: Database session
            chat_id: ID of the chat session
            
        Returns:
            The latest message or None if no messages exist
        """
        query = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


chat_message_repo = ChatMessageRepository() 