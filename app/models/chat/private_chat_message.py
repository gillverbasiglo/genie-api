import enum
import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, Enum  as SQLAlchemyEnum, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import ENUM
from app.database import Base
from enum import Enum

class MessageStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class Message(Base):
    __tablename__ = 'private_chat_messages'
    
    # Message ID
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID for unique message ID
    
    # Sender and receiver relationships
    sender_id = Column(String, ForeignKey('users.id'), nullable=False)  # Foreign key to User table
    receiver_id = Column(String, ForeignKey('users.id'), nullable=False)  # Foreign key to User table (for one-to-one)
    
    # Message content and status
    content = Column(Text, nullable=False)  # The actual message content (text)
    status = Column(ENUM(MessageStatus), default=MessageStatus.SENT)  # Enum field for message status
    
    # Timestamps for created and updated times
    created_at = Column(DateTime, default=datetime.utcnow)  # The time when the message was created
    updated_at = Column(DateTime, onupdate=datetime.utcnow)  # The time when the message was last updated
    
    # Relationships to users (sender and receiver)
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])