from sqlalchemy import Column, String, DateTime, ForeignKey, ARRAY, Boolean, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone

from app.database import Base
from app.schemas.users import UserStatus

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    invited_by = Column(String, ForeignKey("users.id"), nullable=True)
    # Using JSONB for better query performance
    archetypes = Column(JSONB, nullable=True)
    keywords = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)

    # Relationships
    sent_invites = relationship("Invitation", back_populates="inviter", foreign_keys="Invitation.inviter_id", lazy="selectin")
    received_invite = relationship("Invitation", back_populates="invitee", foreign_keys="Invitation.invitee_id", lazy="selectin")

    device_tokens = relationship("DeviceToken", back_populates="user", lazy="selectin")
    sent_shares = relationship("Share", foreign_keys="Share.from_user_id", back_populates="from_user", lazy="selectin")
    received_shares = relationship("Share", foreign_keys="Share.to_user_id", back_populates="to_user", lazy="selectin")
    notifications = relationship("Notification", back_populates="user", lazy="selectin")

    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.from_user_id", back_populates="from_user", lazy="selectin")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.to_user_id", back_populates="to_user", lazy="selectin")
    friends = relationship("Friend", foreign_keys="Friend.user_id", back_populates="user", lazy="selectin")
    friend_of = relationship("Friend", foreign_keys="Friend.friend_id", back_populates="friend", lazy="selectin")

    blocked_users = relationship("UserBlock", foreign_keys="UserBlock.blocker_id", back_populates="blocker", lazy="selectin")
    blocked_by = relationship("UserBlock", foreign_keys="UserBlock.blocked_id", back_populates="blocked", lazy="selectin")

    reports_filed = relationship("UserReport", foreign_keys="UserReport.reporter_id", back_populates="reporter", lazy="selectin")
    reports_received = relationship("UserReport", foreign_keys="UserReport.reported_id", back_populates="reported", lazy="selectin")

    # Relationships
    recommendations = relationship("UserRecommendation", back_populates="user", lazy="selectin")
    locations = relationship("Location", back_populates="user", lazy="selectin")
