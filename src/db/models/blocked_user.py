from datetime import datetime

from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class BlockedUser(Base):
    """Model representing a blocked user relationship."""
    __tablename__ = "blocked_users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # Who blocked
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # Who is blocked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="blocked_users")
    blocked_user = relationship("User", foreign_keys=[blocked_user_id], back_populates="blocked_by") 