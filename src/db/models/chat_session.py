from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class AnonymousChatSession(Base):
    """Model representing an anonymous chat session between matched users."""
    __tablename__ = "anonymous_chat_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True)  # Unique chat identifier
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    status: Mapped[str] = mapped_column(String(20))  # pending, active, ended
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    initiator = relationship("User", foreign_keys=[initiator_id], back_populates="initiated_chats")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_chats")
    match = relationship("Match", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session") 