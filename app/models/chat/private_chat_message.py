import enum
import uuid
from sqlalchemy import JSON, Column, Integer, String, ForeignKey, Enum as SQLAlchemyEnum, DateTime, Text, func
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import ENUM
from app.database import Base
from enum import Enum

class MessageStatus(str, enum.Enum):
    SENT = "sent"        # Message has been sent but not yet delivered
    DELIVERED = "delivered"  # Message has been delivered to recipient
    READ = "read"        # Message has been read by recipient

class MessageType(str, enum.Enum):
    TEXT = "text"    # Plain text messages
    IMAGE = "image"  # Image attachments
    VIDEO = "video"  # Video attachments
    FILE = "file"    # Generic file attachments
    AUDIO = "audio"  # Audio/voice messages

class Message(Base):
    __tablename__ = 'private_chat_messages'
    
    # Primary key and identifiers
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # Unique message identifier
    
    # User relationships
    sender_id = Column(String, ForeignKey('users.id'), nullable=False)  # ID of the message sender
    receiver_id = Column(String, ForeignKey('users.id'), nullable=False)  # ID of the message recipient
    
    # Message content and metadata
    message_type = Column(SQLAlchemyEnum(MessageType), nullable=False, default=MessageType.TEXT)  # Type of message content
    content = Column(Text, nullable=True)  # Text content for text messages
    media_url = Column(String, nullable=True)  # URL or path to media content for non-text messages
    message_meta  = Column(JSON, nullable=True)  # Additional metadata for media messages (e.g., file size, dimensions)

    # Message state and timestamps
    status = Column(ENUM(MessageStatus), default=MessageStatus.SENT)  # Current delivery status
    created_at = Column(DateTime, server_default=func.now())  # Message creation timestamp
    updated_at = Column(DateTime, onupdate=func.now())  # Last update timestamp
    
    # SQLAlchemy relationships
    sender = relationship("User", foreign_keys=[sender_id])  # Relationship to sender user
    receiver = relationship("User", foreign_keys=[receiver_id])  # Relationship to receiver user
    