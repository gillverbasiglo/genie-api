from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP
from .database import Base

class InvitationCode(Base):
    __tablename__ = "invitation_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    created_at = Column(TIMESTAMP, default="now()")
    expires_at = Column(TIMESTAMP, nullable=True)
    used_by = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)