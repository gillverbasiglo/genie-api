from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    invited_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    sent_invites = relationship("Invitation", back_populates="inviter", foreign_keys="Invitation.inviter_id")
    received_invite = relationship("Invitation", back_populates="invitee", foreign_keys="Invitation.invitee_id") 
