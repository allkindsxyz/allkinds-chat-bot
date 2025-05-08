from datetime import datetime
from typing import Optional
from sqlalchemy import Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class UserState(Base):
    """
    Model for storing user state data to persist through app restarts.
    Used for critical operations like points management and matching.
    """
    __tablename__ = "user_states"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    state_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized state data
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="states") 