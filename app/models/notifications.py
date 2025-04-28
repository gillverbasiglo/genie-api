import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from ..database import Base
from sqlalchemy import func

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    type = Column(String)  # share, like, comment, etc.
    title = Column(String)
    message = Column(String)
    data = Column(Text)  # JSON data as string
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="notifications", lazy="selectin")
    
