from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, func
from sqlalchemy.orm import relationship

from src.db.base import Base


class MemberRole(str, Enum):
    """Enum for group member roles."""
    CREATOR = "creator"
    ADMIN = "admin"
    MEMBER = "member"


class GroupMember(Base):
    """GroupMember model for user membership in groups."""

    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), nullable=False, default="member")
    joined_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    photo_file_id = Column(String(255), nullable=True)
    nickname = Column(String(32), nullable=True)

    user = relationship("User", back_populates="group_memberships")
    # group = relationship("Group", back_populates="members")

    def __repr__(self):
        return f"<GroupMember {self.id}: {self.user_id} in {self.group_id} as {self.role}>" 