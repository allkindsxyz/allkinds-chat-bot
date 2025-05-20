from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ChatMessage(Base):
    """Model representing a message in an anonymous chat."""
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content_type: Mapped[str] = mapped_column(String(20))  # text, photo, sticker, etc.
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For media files
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"))
    
    # Relationships
    sender = relationship("User", back_populates="sent_messages")
    chat = relationship("Chat", back_populates="messages") 