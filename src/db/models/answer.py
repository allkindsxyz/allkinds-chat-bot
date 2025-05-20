from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class AnswerType(str, Enum):
    """Enum for answer types."""
    STRONG_NO = "strong_no"
    NO = "no"
    YES = "yes"
    STRONG_YES = "strong_yes"


class Answer(Base):
    """Answer model for storing user answers to questions."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    
    # Answer content
    answer_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False
    )
    
    # Answer numeric value (used for matching algorithm)
    # strong_no = -2, no = -1, yes = 1, strong_yes = 2
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Vector embedding ID in Pinecone
    vector_id: Mapped[str] = mapped_column(String(100), nullable=True, unique=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    
    def __repr__(self) -> str:
        return f"<Answer {self.id}: {self.user_id} -> {self.question_id} = {self.answer_type}>" 