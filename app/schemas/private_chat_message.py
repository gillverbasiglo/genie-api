from pydantic import BaseModel, HttpUrl, field_validator, validator
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

class MessageStatus(str, Enum):
    """
    Attributes:
        SENT: Message has been sent but not yet delivered
        DELIVERED: Message has been delivered to recipient
        READ: Message has been read by recipient
    """
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class MessageType(str, Enum):
    """
    Attributes:
        TEXT: Plain text messages
        IMAGE: Image content with URL
        VIDEO: Video content with URL
        FILE: Generic file attachment
        AUDIO: Audio content with URL
    """
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"
    AUDIO = "audio"

class MessageBase(BaseModel):
    """
    Attributes:
        sender_id: Unique identifier of the message sender
        receiver_id: Unique identifier of the message recipient
        message_type: Type of message content (text, image, etc.)
        content: Optional text content for text messages
        media_url: Optional URL for media content (images, videos, etc.)
        metadata: Optional dictionary for additional message metadata
        status: Current delivery status of the message
        created_at: Timestamp of message creation
        updated_at: Timestamp of last message update
    """
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: Optional[str] = None
    media_url: Optional[HttpUrl] = None
    message_meta: Optional[Dict] = None
    status: MessageStatus = MessageStatus.SENT
    created_at: datetime
    updated_at: datetime


class MessageCreate(MessageBase):
    pass

class MessageOut(MessageBase):
    """
    Attributes:
        id: Unique identifier for the message
        created_at: Optional creation timestamp
        updated_at: Optional last update timestamp
    """
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True  # Enables ORM mode for SQLAlchemy model compatibility
        
class PaginatedMessagesResponse(BaseModel):
    """
    Attributes:
        messages: List of MessageOut objects
        has_more: Boolean indicating if more messages are available
    """
    messages: List[MessageOut]
    has_more: bool


