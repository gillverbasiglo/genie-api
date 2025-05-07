from pydantic import BaseModel, field_validator, validator
from datetime import datetime
from enum import Enum
from typing import List, Optional

class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class MessageBase(BaseModel):
    sender_id: str
    receiver_id: str
    content: str
    status: MessageStatus
    created_at: datetime
    updated_at: datetime


class MessageCreate(MessageBase):
    pass

class MessageOut(MessageBase):
    id: str  # UUID for the message ID

    class Config:
        orm_mode = True  # This allows Pydantic to read data from SQLAlchemy models
        
class PaginatedMessagesResponse(BaseModel):
    messages: List[MessageOut]
    has_more: bool


