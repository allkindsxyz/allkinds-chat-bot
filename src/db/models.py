from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

class UserState(Base):
    """
    Model for storing user state data to persist through app restarts.
    Used for critical operations like points management and matching.
    """
    __tablename__ = "user_states"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    state_data = Column(Text, nullable=False)  # JSON-serialized state data
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="states")


# Update the User model to include the states relationship
User.states = relationship("UserState", back_populates="user", cascade="all, delete-orphan") 