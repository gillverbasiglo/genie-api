from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship
from ..database import Base
from sqlalchemy import func

class Share(Base):
    __tablename__ = "shares"
    
    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"))
    to_user_id = Column(Integer, ForeignKey("users.id"))
    content_id = Column(Integer, index=True)
    content_type = Column(String)
    message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_shares")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="received_shares")
    
