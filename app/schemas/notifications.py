# schemas.py
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum as PyEnum

class NotificationType(str, PyEnum):
    SHARE = "share"
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    FRIEND_REQUEST = "friend_request"

class NotificationBase(BaseModel):
    type: NotificationType
    title: str
    message: str
    data: Optional[str] = None

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationResponse(NotificationBase):
    id: str
    user_id: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationStatusUpdate(BaseModel):
    ids: List[str]
    is_read: bool = True
                