from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional

class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class MessageBase(BaseModel):
    sender_id: str
    receiver_id: str
    content: str
    status: MessageStatus = MessageStatus.SENT
    created_at: datetime
    updated_at: datetime

class MessageCreate(MessageBase):
    pass

class MessageOut(MessageBase):
    id: str  # UUID for the message ID

    class Config:
        from_attributes = True  # This allows Pydantic to read data from SQLAlchemy models
