from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Chat(Base):
    """Model representing a chat between two users in a group."""
    __tablename__ = "chats"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, ended
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # initiator = relationship("User", foreign_keys=[initiator_id], back_populates="initiated_group_chats")
    # recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_group_chats")
    group = relationship("Group", back_populates="chats")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan") 