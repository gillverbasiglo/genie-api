from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base
from app.schemas.friends import FriendRequestStatus

class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    from_user_id = Column(String, ForeignKey("users.id"), index=True)
    to_user_id = Column(String, ForeignKey("users.id"), index=True)
    status = Column(Enum(FriendRequestStatus), default=FriendRequestStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_friend_requests")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="received_friend_requests")
    