from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from ..database import Base
from sqlalchemy import func
import uuid

class Share(Base):
    __tablename__ = "shares"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    from_user_id = Column(String, ForeignKey("users.id"))
    to_user_id = Column(String, ForeignKey("users.id"))
    content_id = Column(String, index=True)
    content_type = Column(String)
    is_Seen = Column(Boolean, default=False)
    message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_shares", lazy="selectin")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="received_shares", lazy="selectin")

    
