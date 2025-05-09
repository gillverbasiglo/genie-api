from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

class UserBlock(Base):
    __tablename__ = "user_blocks"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    blocker_id = Column(String, ForeignKey("users.id"), index=True)
    blocked_id = Column(String, ForeignKey("users.id"), index=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    blocker = relationship("User", foreign_keys=[blocker_id], back_populates="blocked_users")
    blocked = relationship("User", foreign_keys=[blocked_id], back_populates="blocked_by")
    