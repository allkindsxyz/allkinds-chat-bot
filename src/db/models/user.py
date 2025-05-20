from datetime import datetime
from typing import Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class User(Base):
    """User model for storing user data."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # first_name: Mapped[str] = mapped_column(String(64))
    # last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # User state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Points system
    points: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Optional profile fields
    bio: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationships
    created_groups = relationship("Group", back_populates="creator", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="user")
    
    # Match relationships
    matches_as_user1 = relationship("Match", foreign_keys="Match.user1_id", back_populates="user1")
    matches_as_user2 = relationship("Match", foreign_keys="Match.user2_id", back_populates="user2")
    
    # Group chat relationships
    # initiated_group_chats = relationship("Chat", foreign_keys="Chat.initiator_id", back_populates="initiator")
    # received_group_chats = relationship("Chat", foreign_keys="Chat.recipient_id", back_populates="recipient")
    
    # Chat message relationship
    sent_messages = relationship("ChatMessage", back_populates="sender")
    
    # User blocking relationships
    blocked_users = relationship("BlockedUser", foreign_keys="BlockedUser.user_id", back_populates="user")
    blocked_by = relationship("BlockedUser", foreign_keys="BlockedUser.blocked_user_id", back_populates="blocked_user")
    
    # User state persistence
    states: Mapped[List["UserState"]] = relationship("UserState", back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User {self.id} ({self.telegram_user_id})>" 