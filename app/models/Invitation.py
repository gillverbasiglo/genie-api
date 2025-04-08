from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime, timezone

class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(String, primary_key=True, index=True)
    inviter_id = Column(String, ForeignKey("users.id"))
    invitee_phone = Column(String, index=True)
    invitee_email = Column(String, index=True, nullable=True)
    invite_code = Column(String, unique=True, index=True)
    status = Column(String, default="pending")  # pending, accepted, rejected
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    accepted_at = Column(DateTime, nullable=True)
    invitee_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    inviter = relationship("User", back_populates="sent_invites", foreign_keys=[inviter_id])
    invitee = relationship("User", back_populates="received_invite", foreign_keys=[invitee_id]) 
